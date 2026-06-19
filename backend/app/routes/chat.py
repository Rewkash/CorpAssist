import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal, get_db
from app.deps import get_current_user, require_role
from app.models import ChatMessage, Conversation, User
from app.realtime.conversation_snapshots import push_conversations_snapshot
from app.realtime.hubs import ChatSocketHub, UserSocketHub
from app.schemas import (
    ChatMessageItem,
    ConversationItem,
    MarkReadRequest,
    SetConversationTagsRequest,
    SendChatMessageRequest,
)
from app.services.conversation_access import get_accessible_conversation
from app.services.conversation_list import list_conversations_for_user
from app.services.conversation_presenter import build_conversation_items
from app.services.conversation_tags import suggest_conversation_tags_for_user
from app.services.conversation_summarizer import summarize_conversation

logger = logging.getLogger(__name__)

router = APIRouter()

chat_socket_hub: ChatSocketHub | None = None
user_socket_hub: UserSocketHub | None = None


def configure_chat_router(*, chat_hub: ChatSocketHub, user_hub: UserSocketHub) -> None:
    global chat_socket_hub, user_socket_hub
    chat_socket_hub = chat_hub
    user_socket_hub = user_hub


def get_chat_socket_hub() -> ChatSocketHub:
    if chat_socket_hub is None:
        raise RuntimeError('Chat router is not configured')
    return chat_socket_hub


def get_user_socket_hub() -> UserSocketHub:
    if user_socket_hub is None:
        raise RuntimeError('Chat router is not configured')
    return user_socket_hub


@router.get('/chat/conversations', response_model=list[ConversationItem])
async def chat_conversations(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ConversationItem]:
    return await list_conversations_for_user(db, user)


@router.get('/chat/conversations/{conversation_id}/client-history', response_model=list[ConversationItem])
async def client_conversation_history(
    conversation_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ConversationItem]:
    conv_result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    conversation = conv_result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail='Диалог не найден')
    if user.role != 'admin' and user.id not in (conversation.client_id, conversation.worker_id):
        raise HTTPException(status_code=403, detail='Нет доступа к истории клиента')

    result = await db.execute(
        select(Conversation)
        .where(Conversation.client_id == conversation.client_id)
        .order_by(Conversation.created_at.desc())
    )
    rows = result.scalars().all()
    return await build_conversation_items(db, user, rows)


@router.post('/chat/conversations/start', response_model=ConversationItem)
async def start_chat(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationItem:
    user_hub = get_user_socket_hub()
    if user.role != 'client':
        raise HTTPException(status_code=403, detail='Только клиент может начать диалог')
    existing = await db.execute(
        select(Conversation)
        .where(Conversation.client_id == user.id, Conversation.status == 'open')
        .order_by(Conversation.created_at.desc())
    )
    conversation = existing.scalars().first()
    if conversation is None:
        conversation = Conversation(client_id=user.id, worker_id=user.assigned_worker_id, title='Диалог с поддержкой')
        db.add(conversation)
        await db.commit()
        await db.refresh(conversation)
        await push_conversations_snapshot(db, conversation, user_socket_hub=user_hub)
    items = await build_conversation_items(db, user, [conversation])
    return items[0]


@router.post('/chat/conversations/{conversation_id}/take', response_model=ConversationItem)
async def take_conversation(
    conversation_id: int,
    user: User = Depends(require_role('worker', 'admin')),
    db: AsyncSession = Depends(get_db),
) -> ConversationItem:
    user_hub = get_user_socket_hub()
    conv_result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    conversation = conv_result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail='Диалог не найден')
    if user.role == 'worker' and conversation.worker_id and conversation.worker_id != user.id:
        raise HTTPException(status_code=403, detail='Этот диалог уже закреплен за другим сотрудником')
    conversation.worker_id = user.id
    await db.commit()
    await db.refresh(conversation)
    items = await build_conversation_items(db, user, [conversation])
    await push_conversations_snapshot(db, conversation, user_socket_hub=user_hub)
    return items[0]


@router.get('/chat/messages/{conversation_id}', response_model=list[ChatMessageItem])
async def chat_messages(
    conversation_id: int,
    offset: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=500),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ChatMessageItem]:
    await get_accessible_conversation(db, user, conversation_id)

    await db.execute(
        update(ChatMessage)
        .where(ChatMessage.conversation_id == conversation_id, ChatMessage.sender_id != user.id, ChatMessage.status == 'sent')
        .values(status='delivered')
    )
    await db.commit()

    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.conversation_id == conversation_id)
        .order_by(ChatMessage.created_at.asc())
        .offset(offset)
        .limit(limit)
    )
    return [ChatMessageItem.model_validate(row) for row in result.scalars().all()]


@router.post('/chat/messages', response_model=ChatMessageItem)
async def send_chat_message(
    payload: SendChatMessageRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatMessageItem:
    chat_hub = get_chat_socket_hub()
    user_hub = get_user_socket_hub()
    conversation = await get_accessible_conversation(db, user, payload.conversation_id)
    if conversation.status != 'open':
        raise HTTPException(status_code=400, detail='Диалог закрыт. Создайте новый диалог для продолжения.')

    message = ChatMessage(conversation_id=conversation.id, sender_id=user.id, text=payload.text.strip(), status='sent')
    db.add(message)
    await db.commit()
    await db.refresh(message)
    item = ChatMessageItem.model_validate(message)
    await chat_hub.send_to_conversation(
        conversation.id,
        {
            'type': 'message_created',
            'conversation_id': conversation.id,
            'payload': item.model_dump(mode='json'),
        },
    )
    await push_conversations_snapshot(db, conversation, user_socket_hub=user_hub)
    return item


@router.post('/chat/messages/read')
async def mark_messages_read(
    payload: MarkReadRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    chat_hub = get_chat_socket_hub()
    user_hub = get_user_socket_hub()
    conversation = await get_accessible_conversation(db, user, payload.conversation_id)

    await db.execute(
        update(ChatMessage)
        .where(
            ChatMessage.conversation_id == payload.conversation_id,
            ChatMessage.sender_id != user.id,
            ChatMessage.status.in_(['sent', 'delivered']),
        )
        .values(status='read', read_at=func.now())
    )
    await db.commit()
    await chat_hub.send_to_conversation(
        conversation.id,
        {
            'type': 'messages_read',
            'conversation_id': conversation.id,
            'payload': {'viewer_id': user.id},
        },
    )
    await push_conversations_snapshot(db, conversation, user_socket_hub=user_hub)
    return {'status': 'ok'}


@router.post('/chat/conversations/{conversation_id}/close', response_model=ConversationItem)
async def close_conversation(
    conversation_id: int,
    user: User = Depends(require_role('worker', 'admin')),
    db: AsyncSession = Depends(get_db),
) -> ConversationItem:
    user_hub = get_user_socket_hub()
    conv_result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    conversation = conv_result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail='Диалог не найден')
    if conversation.status == 'closed':
        items = await build_conversation_items(db, user, [conversation])
        return items[0]
    if user.role == 'worker' and conversation.worker_id not in (None, user.id):
        raise HTTPException(status_code=403, detail='Нет доступа к закрытию этого диалога')

    conversation.status = 'closed'
    conversation.closed_at = func.now()
    await db.commit()
    await db.refresh(conversation)
    items = await build_conversation_items(db, user, [conversation])
    await push_conversations_snapshot(db, conversation, user_socket_hub=user_hub)

    # Background: generate conversation summary for long-term client memory
    async def _summarize_background() -> None:
        try:
            async with AsyncSessionLocal() as bg_db:
                await summarize_conversation(bg_db, conversation)
        except Exception:
            logger.exception('Background summarization failed for conversation %d', conversation.id)

    asyncio.create_task(_summarize_background())

    return items[0]


@router.get('/chat/conversations/{conversation_id}/suggest-tags')
async def suggest_conversation_tags(
    conversation_id: int,
    user: User = Depends(require_role('worker', 'admin')),
    db: AsyncSession = Depends(get_db),
) -> dict[str, list[str]]:
    user_hub = get_user_socket_hub()

    async def push_snapshot(db: AsyncSession, conversation: Conversation) -> None:
        await push_conversations_snapshot(db, conversation, user_socket_hub=user_hub)

    return await suggest_conversation_tags_for_user(
        db=db,
        conversation_id=conversation_id,
        user=user,
        push_snapshot=push_snapshot,
    )


@router.post('/chat/conversations/{conversation_id}/regenerate-tags')
async def regenerate_conversation_tags(
    conversation_id: int,
    user: User = Depends(require_role('worker', 'admin')),
    db: AsyncSession = Depends(get_db),
) -> dict[str, list[str]]:
    user_hub = get_user_socket_hub()

    async def push_snapshot(db: AsyncSession, conversation: Conversation) -> None:
        await push_conversations_snapshot(db, conversation, user_socket_hub=user_hub)

    return await suggest_conversation_tags_for_user(
        db=db,
        conversation_id=conversation_id,
        user=user,
        push_snapshot=push_snapshot,
        force=True,
    )


@router.post('/chat/conversations/tags', response_model=ConversationItem)
async def set_conversation_tags(
    payload: SetConversationTagsRequest,
    user: User = Depends(require_role('worker', 'admin')),
    db: AsyncSession = Depends(get_db),
) -> ConversationItem:
    user_hub = get_user_socket_hub()
    conv_result = await db.execute(select(Conversation).where(Conversation.id == payload.conversation_id))
    conversation = conv_result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail='Диалог не найден')
    if user.role == 'worker' and conversation.worker_id not in (None, user.id):
        raise HTTPException(status_code=403, detail='Нет доступа к изменению тегов этого диалога')

    normalized_tags: list[str] = []
    for raw_tag in payload.tags:
        tag = raw_tag.strip()
        if tag and tag not in normalized_tags:
            normalized_tags.append(tag)
    conversation.set_tags(normalized_tags)

    has_priority = any(tag.lower() in ('приоритет', 'срочно') for tag in normalized_tags)
    if has_priority and conversation.priority_at is None:
        conversation.priority_at = func.now()
    if not has_priority:
        conversation.priority_at = None

    await db.commit()
    await db.refresh(conversation)
    items = await build_conversation_items(db, user, [conversation])
    await push_conversations_snapshot(db, conversation, user_socket_hub=user_hub)
    return items[0]
