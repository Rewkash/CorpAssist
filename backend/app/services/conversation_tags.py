import json
from collections.abc import Awaitable, Callable

from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.generator import generator_service
from app.models import ChatMessage, Conversation, User
from app.nlp import nlp_service
from app.services.llm_guard import ensure_llm_ready


async def suggest_conversation_tags_for_user(
    *,
    db: AsyncSession,
    conversation_id: int,
    user: User,
    push_snapshot: Callable[[AsyncSession, Conversation], Awaitable[None]],
) -> dict[str, list[str]]:
    ensure_llm_ready()
    conv_result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    conversation = conv_result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail='Диалог не найден')
    if user.role == 'worker' and conversation.worker_id not in (None, user.id):
        raise HTTPException(status_code=403, detail='Нет доступа к диалогу')
    if conversation.tags_generated:
        return {'tags': [], 'applied_tags': []}

    msg_result = await db.execute(
        select(ChatMessage).where(ChatMessage.conversation_id == conversation_id).order_by(ChatMessage.created_at.asc())
    )
    messages = msg_result.scalars().all()
    if not messages:
        return {'tags': [], 'applied_tags': []}

    client_messages = [m for m in messages if m.sender_id == conversation.client_id]
    client_text_len = sum(len((m.text or '').strip()) for m in client_messages)
    if len(client_messages) < 2 or client_text_len < 50:
        return {'tags': [], 'applied_tags': []}

    full_text = '\n'.join(
        [
            f'Клиент: {m.text}' if m.sender_id == conversation.client_id else f'Оператор: {m.text}'
            for m in messages
        ]
    )[:8000]

    ai_result = await generator_service.suggest_tags(full_text)
    auto_tags = [tag.strip() for tag in ai_result.get('auto_tags', []) if tag.strip()]
    suggested_tags = [tag.strip() for tag in ai_result.get('suggested_tags', []) if tag.strip()]
    priority = bool(ai_result.get('priority', False))

    applied_tags: list[str] = []
    for tag in auto_tags:
        if tag not in applied_tags:
            applied_tags.append(tag)
    if priority and 'Срочно' not in applied_tags:
        applied_tags.append('Срочно')

    if applied_tags:
        conversation.tags = json.dumps(applied_tags, ensure_ascii=False)
        conversation.tags_generated = True
        if 'Срочно' in applied_tags and conversation.priority_at is None:
            await db.execute(text('UPDATE conversations SET priority_at = NOW() WHERE id = :id'), {'id': conversation.id})
        if 'Срочно' not in applied_tags:
            conversation.priority_at = None
        await db.commit()
        await db.refresh(conversation)
        await push_snapshot(db, conversation)
        return {'tags': suggested_tags, 'applied_tags': applied_tags}

    analysis = await nlp_service.analyze(full_text)
    tags: list[str] = []
    for topic in analysis.topics[:5]:
        topic_clean = topic.strip().capitalize()
        if topic_clean and topic_clean not in tags:
            tags.append(topic_clean)
    if analysis.sentiment == 'tense' and 'Приоритет' not in tags:
        tags.insert(0, 'Приоритет')
    applied_fallback = tags[:2]
    if applied_fallback:
        conversation.tags = json.dumps(applied_fallback, ensure_ascii=False)
        conversation.tags_generated = True
        await db.commit()
        await db.refresh(conversation)
        await push_snapshot(db, conversation)
    return {'tags': [], 'applied_tags': applied_fallback}
