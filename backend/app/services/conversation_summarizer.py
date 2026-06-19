"""Summarize a closed conversation and persist the summary for long-term client memory."""

import logging
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.generator import generator_service
from app.models import ChatMessage, Conversation, ConversationSummary
from app.prompts.llm_prompts import SYSTEM_PROMPT_SUMMARIZE
from app.services.client_memory import update_client_profile_from_summary
from app.services.embedding_service import embed_conversation_summary

logger = logging.getLogger(__name__)

# Maximum conversation text length sent to LLM for summarization
MAX_CONVERSATION_TEXT = 6000


def _parse_summary(raw: str) -> dict:
    """Parse LLM output into structured summary fields."""
    result = {
        'summary': '',
        'key_topics': [],
        'resolution': '',
        'sentiment_trend': '',
    }

    # Parse each line
    for line in raw.strip().splitlines():
        line = line.strip()
        if line.upper().startswith('САММАРИ:') or line.upper().startswith('SUMMARY:'):
            result['summary'] = line.split(':', 1)[1].strip() if ':' in line else ''
        elif line.upper().startswith('ТЕМЫ:') or line.upper().startswith('TOPICS:'):
            topics_str = line.split(':', 1)[1].strip() if ':' in line else ''
            if topics_str:
                result['key_topics'] = [t.strip() for t in topics_str.split(',') if t.strip()][:5]
        elif line.upper().startswith('РЕЗУЛЬТАТ:') or line.upper().startswith('RESOLUTION:'):
            result['resolution'] = line.split(':', 1)[1].strip() if ':' in line else ''
        elif line.upper().startswith('НАСТРОЕНИЕ:') or line.upper().startswith('SENTIMENT:'):
            result['sentiment_trend'] = line.split(':', 1)[1].strip() if ':' in line else ''

    # Fallback: if no structured lines found, use entire raw text as summary
    if not result['summary']:
        clean = re.sub(r'^(САММАРИ|ТЕМЫ|РЕЗУЛЬТАТ|НАСТРОЕНИЕ):.*$', '', raw, flags=re.MULTILINE).strip()
        if clean:
            result['summary'] = clean[:500]

    return result


def _build_conversation_text(conversation: Conversation, messages: list[ChatMessage]) -> str:
    """Format conversation messages into a compact transcript for the LLM."""
    lines: list[str] = []
    client_id = conversation.client_id
    for msg in messages:
        role = 'Клиент' if msg.sender_id == client_id else 'Оператор'
        # Truncate very long messages
        text = msg.text[:500] if len(msg.text) > 500 else msg.text
        lines.append(f'{role}: {text}')
    transcript = '\n'.join(lines)
    if len(transcript) > MAX_CONVERSATION_TEXT:
        transcript = transcript[:MAX_CONVERSATION_TEXT] + '\n...(обрезано)'
    return transcript


async def summarize_conversation(db: AsyncSession, conversation: Conversation) -> ConversationSummary | None:
    """Generate and persist a summary for a closed conversation.

    This is designed to run as a background task (fire-and-forget).
    It creates its own error handling and never raises to the caller.
    """
    if conversation.status != 'closed':
        logger.debug('Skipping summary for open conversation %d', conversation.id)
        return None

    # Check if summary already exists
    existing = await db.execute(
        select(ConversationSummary).where(ConversationSummary.conversation_id == conversation.id)
    )
    if existing.scalar_one_or_none():
        logger.debug('Summary already exists for conversation %d', conversation.id)
        return None

    # Fetch messages
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.conversation_id == conversation.id)
        .order_by(ChatMessage.created_at.asc())
    )
    messages = list(result.scalars().all())

    if len(messages) < 2:
        logger.debug('Too few messages to summarize conversation %d', conversation.id)
        return None

    # Build transcript
    transcript = _build_conversation_text(conversation, messages)

    # Call LLM
    try:
        raw = await generator_service._llm.generate(
            system_prompt=SYSTEM_PROMPT_SUMMARIZE,
            user_prompt=f'ДIALOG:\n{transcript}',
            temperature=0.1,
            max_tokens=300,
            mode='summarize_conversation',
        )
    except Exception:
        logger.exception('LLM summarization failed for conversation %d', conversation.id)
        # Create a basic fallback summary from messages
        raw = _make_fallback_summary(conversation, messages)

    parsed = _parse_summary(raw)

    # Persist
    summary = ConversationSummary(
        conversation_id=conversation.id,
        client_id=conversation.client_id,
        summary=parsed['summary'] or 'Саммари недоступно',
        resolution=parsed['resolution'],
        sentiment_trend=parsed['sentiment_trend'],
    )
    summary.set_key_topics(parsed['key_topics'])
    db.add(summary)

    # Update client profile
    try:
        await update_client_profile_from_summary(db, conversation.client_id, summary)
    except Exception:
        logger.exception('Failed to update client profile for client_id=%d', conversation.client_id)

    try:
        await db.commit()
    except Exception:
        logger.exception('Failed to commit summary for conversation %d', conversation.id)
        await db.rollback()
        return None

    # Generate and store vector embedding (async, non-blocking for main flow)
    try:
        await embed_conversation_summary(db, generator_service._llm, summary)
        await db.commit()
    except Exception:
        logger.debug('Embedding generation failed for summary %d (non-critical)', summary.id)

    logger.info(
        'Generated summary for conversation %d (client_id=%d, topics=%s)',
        conversation.id, conversation.client_id, parsed['key_topics'],
    )
    return summary


def _make_fallback_summary(conversation: Conversation, messages: list[ChatMessage]) -> str:
    """Create a basic summary without LLM when it's unavailable."""
    client_msgs = [m for m in messages if m.sender_id == conversation.client_id]
    operator_msgs = [m for m in messages if m.sender_id != conversation.client_id]

    # Take first and last client message as summary
    parts: list[str] = []
    if client_msgs:
        first = client_msgs[0].text[:150]
        parts.append(f'Клиент обратился: {first}')
        if len(client_msgs) > 1:
            last = client_msgs[-1].text[:150]
            parts.append(f'Последнее сообщение: {last}')

    topic_guess = conversation.title if conversation.title != 'Новый диалог' else ''
    resolution = 'Не решено' if conversation.status == 'closed' and not operator_msgs else 'Решено'

    lines = [f'САММАРИ: {" ".join(parts)}']
    if topic_guess:
        lines.append(f'ТЕМЫ: {topic_guess}')
    lines.append(f'РЕЗУЛЬТАТ: {resolution}')
    lines.append('НАСТРОЕНИЕ: стабильное нейтральное')

    return '\n'.join(lines)
