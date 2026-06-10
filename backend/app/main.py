import json
from collections import defaultdict
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

import httpx
from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import decode_access_token
from app.config import settings
from app.database import AsyncSessionLocal, Base, engine, get_db
from app.deps import get_current_user, require_role
from app.generator import generator_service
from app.models import ChatMessage, Conversation, MessageHistory, User
from app.nlp import nlp_service
from app.routes import admin, auth, debug_llm
from app.schemas import (
    ChatMessageItem,
    ConversationItem,
    HistoryItem,
    ImproveDraftRequest,
    ImproveDraftResponse,
    MarkReadRequest,
    SetConversationTagsRequest,
    SendChatMessageRequest,
    SuggestReplyRequest,
    SuggestReplyResponse,
)


async def build_client_context(db: AsyncSession, client_id: int) -> str:
    result = await db.execute(
        select(ChatMessage)
        .join(Conversation, Conversation.id == ChatMessage.conversation_id)
        .where(Conversation.client_id == client_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(20)
    )
    items = result.scalars().all()
    result_lines: list[str] = []
    for item in reversed(items):
        role = 'Клиент' if item.sender_id == client_id else 'Оператор'
        result_lines.append(f'{role}: {item.text}')
    return '\n'.join(result_lines)


async def build_conversation_context(db: AsyncSession, conversation: Conversation) -> str:
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.conversation_id == conversation.id)
        .order_by(ChatMessage.created_at.desc())
        .limit(30)
    )
    items = result.scalars().all()
    result_lines: list[str] = []
    for item in reversed(items):
        role = 'Клиент' if item.sender_id == conversation.client_id else 'Оператор'
        result_lines.append(f'{role}: {item.text}')
    return '\n'.join(result_lines)


def ensure_llm_ready() -> None:
    try:
        generator_service.ensure_ready()
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(20) DEFAULT 'client'"))
        await conn.execute(text('ALTER TABLE users ADD COLUMN IF NOT EXISTS assigned_worker_id INTEGER'))
        await conn.execute(text('ALTER TABLE conversations ALTER COLUMN worker_id DROP NOT NULL'))
        await conn.execute(text("ALTER TABLE conversations ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'open'"))
        await conn.execute(text('ALTER TABLE conversations ADD COLUMN IF NOT EXISTS closed_at TIMESTAMPTZ NULL'))
        await conn.execute(text("ALTER TABLE conversations ADD COLUMN IF NOT EXISTS tags TEXT DEFAULT '[]'"))
        await conn.execute(text('ALTER TABLE conversations ADD COLUMN IF NOT EXISTS tags_generated BOOLEAN DEFAULT FALSE'))
        await conn.execute(text('ALTER TABLE conversations ADD COLUMN IF NOT EXISTS priority_at TIMESTAMPTZ NULL'))
        await conn.execute(text("ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'sent'"))
        await conn.execute(text('ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS read_at TIMESTAMPTZ NULL'))
        await conn.execute(text('CREATE INDEX IF NOT EXISTS ix_chat_messages_status ON chat_messages (status)'))
        await conn.execute(text('CREATE INDEX IF NOT EXISTS ix_conversations_status ON conversations (status)'))
        await conn.execute(text('CREATE INDEX IF NOT EXISTS ix_conversations_priority_at ON conversations (priority_at)'))
        await conn.execute(text('CREATE INDEX IF NOT EXISTS ix_users_role ON users (role)'))
        await conn.execute(text('CREATE INDEX IF NOT EXISTS ix_users_assigned_worker_id ON users (assigned_worker_id)'))
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(debug_llm.router)


@dataclass(frozen=True)
class ChatSocketClient:
    user_id: int
    role: str
    websocket: WebSocket


class ChatSocketHub:
    def __init__(self) -> None:
        self._conversation_rooms: dict[int, set[ChatSocketClient]] = defaultdict(set)
        self._user_connections: dict[int, set[ChatSocketClient]] = defaultdict(set)

    def connect(self, conversation_id: int, client: ChatSocketClient) -> None:
        self._conversation_rooms[conversation_id].add(client)
        self._user_connections[client.user_id].add(client)

    def disconnect(self, conversation_id: int, client: ChatSocketClient) -> None:
        room = self._conversation_rooms.get(conversation_id)
        if room and client in room:
            room.remove(client)
            if not room:
                self._conversation_rooms.pop(conversation_id, None)
        user_sockets = self._user_connections.get(client.user_id)
        if user_sockets and client in user_sockets:
            user_sockets.remove(client)
            if not user_sockets:
                self._user_connections.pop(client.user_id, None)

    async def send_to_conversation(self, conversation_id: int, payload: dict[str, Any]) -> None:
        targets = list(self._conversation_rooms.get(conversation_id, set()))
        for client in targets:
            try:
                await client.websocket.send_json(payload)
            except Exception:
                self.disconnect(conversation_id, client)

    async def send_to_user(self, user_id: int, payload: dict[str, Any]) -> None:
        targets = list(self._user_connections.get(user_id, set()))
        for client in targets:
            try:
                await client.websocket.send_json(payload)
            except Exception:
                for conversation_id, room in list(self._conversation_rooms.items()):
                    if client in room:
                        self.disconnect(conversation_id, client)


chat_socket_hub = ChatSocketHub()


class UserSocketHub:
    def __init__(self) -> None:
        self._connections: dict[int, set[WebSocket]] = defaultdict(set)

    def connect(self, user_id: int, websocket: WebSocket) -> None:
        self._connections[user_id].add(websocket)

    def disconnect(self, user_id: int, websocket: WebSocket) -> None:
        sockets = self._connections.get(user_id)
        if not sockets:
            return
        if websocket in sockets:
            sockets.remove(websocket)
        if not sockets:
            self._connections.pop(user_id, None)

    async def send_to_user(self, user_id: int, payload: dict[str, Any]) -> None:
        targets = list(self._connections.get(user_id, set()))
        for websocket in targets:
            try:
                await websocket.send_json(payload)
            except Exception:
                self.disconnect(user_id, websocket)


user_socket_hub = UserSocketHub()


async def build_conversation_items(db: AsyncSession, user: User, rows: list[Conversation]) -> list[ConversationItem]:
    client_ids = {row.client_id for row in rows}
    client_emails: dict[int, str] = {}
    if client_ids:
        client_result = await db.execute(select(User.id, User.email).where(User.id.in_(client_ids)))
        client_emails = {row.id: row.email for row in client_result.all()}
    items: list[ConversationItem] = []
    for row in rows:
        unread_result = await db.execute(
            text(
                """
                SELECT COUNT(*)
                FROM chat_messages
                WHERE conversation_id = :conversation_id
                  AND sender_id != :viewer_id
                  AND status IN ('sent', 'delivered')
                """
            ),
            {'conversation_id': row.id, 'viewer_id': user.id},
        )
        unread_count = int(unread_result.scalar_one() or 0)
        msg_count_result = await db.execute(
            text('SELECT COUNT(*) FROM chat_messages WHERE conversation_id = :conversation_id'),
            {'conversation_id': row.id},
        )
        message_count = int(msg_count_result.scalar_one() or 0)
        preview_result = await db.execute(
            text(
                """
                SELECT text
                FROM chat_messages
                WHERE conversation_id = :conversation_id
                ORDER BY created_at ASC
                LIMIT 1
                """
            ),
            {'conversation_id': row.id},
        )
        first_message_preview = preview_result.scalar_one_or_none()
        parsed_tags: list[str] = []
        if row.tags:
            try:
                loaded = json.loads(row.tags)
                if isinstance(loaded, list):
                    parsed_tags = [str(tag).strip() for tag in loaded if str(tag).strip()]
            except Exception:
                parsed_tags = []
        items.append(
            ConversationItem(
                id=row.id,
                title=row.title,
                client_id=row.client_id,
                client_email=client_emails.get(row.client_id),
                worker_id=row.worker_id,
                status=row.status,
                unread_count=unread_count,
                tags=parsed_tags,
                priority_at=row.priority_at,
                message_count=message_count,
                first_message_preview=first_message_preview,
                created_at=row.created_at,
                closed_at=row.closed_at,
            )
        )
    return items


async def resolve_ws_user(websocket: WebSocket, db: AsyncSession) -> User | None:
    token = websocket.query_params.get('token')
    email = decode_access_token(token) if token else None
    if not email:
        return None
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_accessible_conversation(db: AsyncSession, user: User, conversation_id: int) -> Conversation:
    conv_result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    conversation = conv_result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail='Диалог не найден')
    if user.role != 'admin' and user.id not in (conversation.client_id, conversation.worker_id):
        raise HTTPException(status_code=403, detail='Нет доступа к диалогу')
    return conversation


async def push_conversations_snapshot(db: AsyncSession, conversation: Conversation) -> None:
    target_user_ids = {conversation.client_id}
    if conversation.worker_id:
        target_user_ids.add(conversation.worker_id)

    admin_result = await db.execute(select(User.id).where(User.role == 'admin'))
    target_user_ids.update(row.id for row in admin_result.all())

    for user_id in target_user_ids:
        user_result = await db.execute(select(User).where(User.id == user_id))
        viewer = user_result.scalar_one_or_none()
        if not viewer:
            continue
        items = await chat_conversations(user=viewer, db=db)
        await user_socket_hub.send_to_user(
            user_id,
            {
                'type': 'conversations_snapshot',
                'payload': [item.model_dump(mode='json') for item in items],
            },
        )


@app.get('/health')
async def health() -> dict[str, Any]:
    ollama_ok = False
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f'{settings.ollama_base_url}/api/tags')
            ollama_ok = resp.status_code == 200
    except Exception:
        pass
    return {'status': 'ok', 'ollama': 'connected' if ollama_ok else 'unavailable'}


@app.get('/chat/conversations', response_model=list[ConversationItem])
async def chat_conversations(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ConversationItem]:
    if user.role == 'client':
        result = await db.execute(
            select(Conversation)
            .where(Conversation.client_id == user.id)
            .order_by(Conversation.priority_at.asc().nullslast(), Conversation.created_at.desc())
        )
    elif user.role == 'worker':
        result = await db.execute(
            select(Conversation)
            .where((Conversation.worker_id == user.id) | ((Conversation.worker_id.is_(None)) & (Conversation.status == 'open')))
            .order_by(Conversation.priority_at.asc().nullslast(), Conversation.created_at.desc())
        )
    else:
        result = await db.execute(
            select(Conversation)
            .order_by(Conversation.priority_at.asc().nullslast(), Conversation.created_at.desc())
            .limit(100)
        )
    rows = result.scalars().all()
    return await build_conversation_items(db, user, rows)


@app.get('/chat/conversations/{conversation_id}/client-history', response_model=list[ConversationItem])
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


@app.post('/chat/conversations/start', response_model=ConversationItem)
async def start_chat(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationItem:
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
        await push_conversations_snapshot(db, conversation)
    items = await build_conversation_items(db, user, [conversation])
    return items[0]


@app.post('/chat/conversations/{conversation_id}/take', response_model=ConversationItem)
async def take_conversation(
    conversation_id: int,
    user: User = Depends(require_role('worker', 'admin')),
    db: AsyncSession = Depends(get_db),
) -> ConversationItem:
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
    await push_conversations_snapshot(db, conversation)
    return items[0]


@app.get('/chat/messages/{conversation_id}', response_model=list[ChatMessageItem])
async def chat_messages(
    conversation_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ChatMessageItem]:
    await get_accessible_conversation(db, user, conversation_id)

    await db.execute(
        text(
            """
            UPDATE chat_messages
            SET status = 'delivered'
            WHERE conversation_id = :conversation_id
              AND sender_id != :viewer_id
              AND status = 'sent'
            """
        ),
        {'conversation_id': conversation_id, 'viewer_id': user.id},
    )
    await db.commit()

    result = await db.execute(select(ChatMessage).where(ChatMessage.conversation_id == conversation_id).order_by(ChatMessage.created_at.asc()))
    return [ChatMessageItem.model_validate(row) for row in result.scalars().all()]


@app.post('/chat/messages', response_model=ChatMessageItem)
async def send_chat_message(
    payload: SendChatMessageRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatMessageItem:
    conversation = await get_accessible_conversation(db, user, payload.conversation_id)
    if conversation.status != 'open':
        raise HTTPException(status_code=400, detail='Диалог закрыт. Создайте новый диалог для продолжения.')

    message = ChatMessage(conversation_id=conversation.id, sender_id=user.id, text=payload.text.strip(), status='sent')
    db.add(message)
    await db.commit()
    await db.refresh(message)
    item = ChatMessageItem.model_validate(message)
    await chat_socket_hub.send_to_conversation(
        conversation.id,
        {
            'type': 'message_created',
            'conversation_id': conversation.id,
            'payload': item.model_dump(mode='json'),
        },
    )
    await push_conversations_snapshot(db, conversation)
    return item


@app.post('/chat/messages/read')
async def mark_messages_read(
    payload: MarkReadRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    conversation = await get_accessible_conversation(db, user, payload.conversation_id)

    await db.execute(
        text(
            """
            UPDATE chat_messages
            SET status = 'read', read_at = NOW()
            WHERE conversation_id = :conversation_id
              AND sender_id != :viewer_id
              AND status IN ('sent', 'delivered')
            """
        ),
        {'conversation_id': payload.conversation_id, 'viewer_id': user.id},
    )
    await db.commit()
    await chat_socket_hub.send_to_conversation(
        conversation.id,
        {
            'type': 'messages_read',
            'conversation_id': conversation.id,
            'payload': {'viewer_id': user.id},
        },
    )
    await push_conversations_snapshot(db, conversation)
    return {'status': 'ok'}


@app.post('/chat/conversations/{conversation_id}/close', response_model=ConversationItem)
async def close_conversation(
    conversation_id: int,
    user: User = Depends(require_role('worker', 'admin')),
    db: AsyncSession = Depends(get_db),
) -> ConversationItem:
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
    await db.execute(text('UPDATE conversations SET closed_at = NOW() WHERE id = :id'), {'id': conversation.id})
    await db.commit()
    await db.refresh(conversation)
    items = await build_conversation_items(db, user, [conversation])
    await push_conversations_snapshot(db, conversation)
    return items[0]


@app.get('/chat/conversations/{conversation_id}/suggest-tags')
async def suggest_conversation_tags(
    conversation_id: int,
    user: User = Depends(require_role('worker', 'admin')),
    db: AsyncSession = Depends(get_db),
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
        await push_conversations_snapshot(db, conversation)
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
        await push_conversations_snapshot(db, conversation)
    return {'tags': [], 'applied_tags': applied_fallback}


@app.post('/chat/conversations/tags', response_model=ConversationItem)
async def set_conversation_tags(
    payload: SetConversationTagsRequest,
    user: User = Depends(require_role('worker', 'admin')),
    db: AsyncSession = Depends(get_db),
) -> ConversationItem:
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
    conversation.tags = json.dumps(normalized_tags, ensure_ascii=False)

    has_priority = any(tag.lower() in ('приоритет', 'срочно') for tag in normalized_tags)
    if has_priority and conversation.priority_at is None:
        await db.execute(text('UPDATE conversations SET priority_at = NOW() WHERE id = :id'), {'id': conversation.id})
    if not has_priority:
        conversation.priority_at = None

    await db.commit()
    await db.refresh(conversation)
    items = await build_conversation_items(db, user, [conversation])
    await push_conversations_snapshot(db, conversation)
    return items[0]


@app.post('/assist/reply', response_model=SuggestReplyResponse)
async def suggest_reply(
    payload: SuggestReplyRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SuggestReplyResponse:
    ensure_llm_ready()
    analysis = await nlp_service.analyze(payload.text)
    context = ''
    if user.role == 'client':
        context = await build_client_context(db, user.id)
    elif user.role == 'worker' and payload.conversation_id:
        conv_result = await db.execute(select(Conversation).where(Conversation.id == payload.conversation_id))
        conv = conv_result.scalar_one_or_none()
        if conv and conv.client_id:
            context = await build_conversation_context(db, conv)
    suggestions = await generator_service.suggest_replies(payload.text, analysis, context)

    response = SuggestReplyResponse(analysis=analysis, suggestions=suggestions)

    db.add(
        MessageHistory(
            user_id=user.id,
            mode='reply',
            source_text=payload.text,
            result_text='\n---\n'.join(suggestions),
            sentiment=analysis.sentiment,
            topics=', '.join(analysis.topics),
            formality=analysis.formality,
        )
    )
    await db.commit()
    return response


@app.post('/assist/improve', response_model=ImproveDraftResponse)
async def improve_draft(
    payload: ImproveDraftRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ImproveDraftResponse:
    ensure_llm_ready()
    analysis = await nlp_service.analyze(payload.text)
    context = ''
    if user.role == 'client':
        context = await build_client_context(db, user.id)
    elif user.role == 'worker' and payload.conversation_id:
        conv_result = await db.execute(select(Conversation).where(Conversation.id == payload.conversation_id))
        conv = conv_result.scalar_one_or_none()
        if conv and conv.client_id:
            context = await build_conversation_context(db, conv)
    improved = await generator_service.improve_draft(payload.text, analysis, context)
    diff = nlp_service.make_diff(payload.text, improved)

    response = ImproveDraftResponse(analysis=analysis, improved_text=improved, diff=diff)

    db.add(
        MessageHistory(
            user_id=user.id,
            mode='improve',
            source_text=payload.text,
            result_text=improved,
            sentiment=analysis.sentiment,
            topics=', '.join(analysis.topics),
            formality=analysis.formality,
        )
    )
    await db.commit()
    return response


@app.get('/history', response_model=list[HistoryItem])
async def history(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[HistoryItem]:
    result = await db.execute(
        select(MessageHistory).where(MessageHistory.user_id == user.id).order_by(MessageHistory.created_at.desc()).limit(30)
    )
    return [HistoryItem.model_validate(row) for row in result.scalars().all()]


@app.websocket('/ws/chat/{conversation_id}')
async def chat_ws(websocket: WebSocket, conversation_id: int):
    async with AsyncSessionLocal() as db:
        user = await resolve_ws_user(websocket, db)
        if not user:
            await websocket.close(code=1008)
            return

        try:
            await get_accessible_conversation(db, user, conversation_id)
        except HTTPException:
            await websocket.close(code=1008)
            return

    await websocket.accept()
    client = ChatSocketClient(user_id=user.id, role=user.role, websocket=websocket)
    chat_socket_hub.connect(conversation_id, client)
    try:
        await websocket.send_json({'type': 'connected', 'conversation_id': conversation_id})
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        chat_socket_hub.disconnect(conversation_id, client)


@app.websocket('/ws/chat-updates')
async def chat_updates_ws(websocket: WebSocket):
    async with AsyncSessionLocal() as db:
        user = await resolve_ws_user(websocket, db)
        if not user:
            await websocket.close(code=1008)
            return

    await websocket.accept()
    user_socket_hub.connect(user.id, websocket)
    try:
        await websocket.send_json({'type': 'connected', 'scope': 'updates'})
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        user_socket_hub.disconnect(user.id, websocket)


@app.websocket('/ws/assist')
async def assist_ws(websocket: WebSocket):
    token = websocket.query_params.get('token')
    email = decode_access_token(token) if token else None
    if not email:
        await websocket.close(code=1008)
        return

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if not user:
            await websocket.close(code=1008)
            return

    await websocket.accept()
    try:
        while True:
            raw = await websocket.receive_text()
            payload = json.loads(raw)
            mode = payload.get('mode')
            text = (payload.get('text') or '').strip()
            conversation_id = payload.get('conversation_id')
            if len(text) < 5:
                await websocket.send_json({'type': 'error', 'message': 'Введите более содержательный текст'})
                continue
            if generator_service.model_loading:
                await websocket.send_json({'type': 'error', 'message': generator_service.model_status})
                continue

            analysis = await nlp_service.analyze(text)
            await websocket.send_json({'type': 'analysis', 'payload': analysis.model_dump()})
            await websocket.send_json({'type': 'generating', 'message': 'Генерация ответа нейросетью...'})

            if mode == 'reply':
                context = ''
                if user.role == 'client':
                    context = await build_client_context(db, user.id)
                elif user.role == 'worker' and conversation_id:
                    conv_result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
                    conv = conv_result.scalar_one_or_none()
                    if conv and conv.client_id:
                        context = await build_client_context(db, conv.client_id)
                suggestions = await generator_service.suggest_replies(text, analysis, context)
                await websocket.send_json({'type': 'reply_suggestions', 'payload': suggestions})
            elif mode == 'improve':
                improved = await generator_service.improve_draft(text, analysis)
                diff = [chunk.model_dump() for chunk in nlp_service.make_diff(text, improved)]
                await websocket.send_json({'type': 'improved', 'payload': {'text': improved, 'diff': diff}})
            else:
                await websocket.send_json({'type': 'error', 'message': 'Неизвестная команда'})
    except WebSocketDisconnect:
        return
