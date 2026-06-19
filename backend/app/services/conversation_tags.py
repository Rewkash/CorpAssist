from collections.abc import Awaitable, Callable

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.generator import generator_service
from app.models import ChatMessage, Conversation, User
from app.nlp import nlp_service
from app.services.llm_guard import ensure_llm_ready

MIN_CLIENT_MSG_LENGTH = 80  # минимум символов в одном сообщении для ранней активации
MIN_TOTAL_CLIENT_LENGTH = 50  # минимум суммарной длины для активации после обмена


async def suggest_conversation_tags_for_user(
    *,
    db: AsyncSession,
    conversation_id: int,
    user: User,
    push_snapshot: Callable[[AsyncSession, Conversation], Awaitable[None]],
    force: bool = False,
) -> dict[str, list[str]]:
    ensure_llm_ready()
    conv_result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    conversation = conv_result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail='Диалог не найден')
    if user.role == 'worker' and conversation.worker_id not in (None, user.id):
        raise HTTPException(status_code=403, detail='Нет доступа к диалогу')
    if conversation.tags_generated and not force:
        return {'tags': [], 'applied_tags': []}

    msg_result = await db.execute(
        select(ChatMessage).where(ChatMessage.conversation_id == conversation_id).order_by(ChatMessage.created_at.asc())
    )
    messages = msg_result.scalars().all()
    if not messages:
        return {'tags': [], 'applied_tags': []}

    client_messages = [m for m in messages if m.sender_id == conversation.client_id]
    client_text_len = sum(len((m.text or '').strip()) for m in client_messages)

    has_long_client_msg = any(
        len((m.text or '').strip()) >= MIN_CLIENT_MSG_LENGTH for m in client_messages
    )

    operator_replied_between_clients = False
    if len(client_messages) >= 2:
        first_client_index = next(
            i for i, m in enumerate(messages) if m.sender_id == conversation.client_id
        )
        last_client_index = len(messages) - 1 - next(
            i for i, m in enumerate(reversed(messages)) if m.sender_id == conversation.client_id
        )
        operator_replied_between_clients = any(
            m.sender_id != conversation.client_id
            for m in messages[first_client_index + 1:last_client_index]
        )

    has_dialog_exchange = (
        len(client_messages) >= 2
        and operator_replied_between_clients
        and client_text_len >= MIN_TOTAL_CLIENT_LENGTH
    )

    if not (has_long_client_msg or has_dialog_exchange):
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
        conversation.set_tags(applied_tags)
        conversation.tags_generated = True
        if 'Срочно' in applied_tags and conversation.priority_at is None:
            conversation.priority_at = func.now()
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
        conversation.set_tags(applied_fallback)
        conversation.tags_generated = True
        await db.commit()
        await db.refresh(conversation)
        await push_snapshot(db, conversation)
    return {'tags': [], 'applied_tags': applied_fallback}
