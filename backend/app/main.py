import json
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import decode_access_token
from app.config import settings
from app.database import AsyncSessionLocal
from app.generator import generator_service
from app.models import Conversation, User
from app.nlp import nlp_service
from app.realtime.hubs import ChatSocketClient, ChatSocketHub, UserSocketHub
from app.routes import admin, assist, auth, chat, debug_llm
from app.services.assist_context import build_client_context
from app.services.conversation_access import get_accessible_conversation


@asynccontextmanager
async def lifespan(_: FastAPI):
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
app.include_router(assist.router)
app.include_router(chat.router)
if settings.enable_llm_debug:
    app.include_router(debug_llm.router)


chat_socket_hub = ChatSocketHub()


user_socket_hub = UserSocketHub()


chat.configure_chat_router(chat_hub=chat_socket_hub, user_hub=user_socket_hub)


async def resolve_ws_user(websocket: WebSocket, db: AsyncSession) -> User | None:
    token = websocket.query_params.get('token')
    email = decode_access_token(token) if token else None
    if not email:
        return None
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


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
