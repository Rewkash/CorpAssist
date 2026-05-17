"""Бэкфилл базы знаний: индексирует уже накопленные чаты и KnowledgeEntry.

Запуск (внутри контейнера backend):
    python -m app.backfill_knowledge
"""
from __future__ import annotations

import asyncio
import json
import logging

from sqlalchemy import select

from app import knowledge as knowledge_service
from app.database import AsyncSessionLocal
from app.models import ChatMessage, Conversation, KnowledgeChunk, KnowledgeEntry

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger('backfill_knowledge')


async def backfill_chat_messages() -> int:
    indexed = 0
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ChatMessage, Conversation)
            .join(Conversation, Conversation.id == ChatMessage.conversation_id)
            .order_by(ChatMessage.id.asc())
        )
        rows = result.all()
    logger.info('Найдено сообщений в чате: %s', len(rows))

    for message, conversation in rows:
        text = (message.text or '').strip()
        if len(text) < 30 or conversation.client_id is None:
            continue
        async with AsyncSessionLocal() as db:
            existing = await db.execute(
                select(KnowledgeChunk).where(
                    (KnowledgeChunk.source_type == knowledge_service.SOURCE_CHAT)
                    & (KnowledgeChunk.source_id == message.id)
                )
            )
            if existing.scalar_one_or_none() is not None:
                continue
            try:
                await knowledge_service.index_text(
                    db,
                    text=text,
                    source_type=knowledge_service.SOURCE_CHAT,
                    source_id=message.id,
                    scope=knowledge_service.SCOPE_CLIENT,
                    client_id=conversation.client_id,
                    meta={'conversation_id': conversation.id},
                )
                indexed += 1
            except Exception:  # noqa: BLE001
                logger.exception('Не удалось проиндексировать сообщение %s', message.id)
    return indexed


async def backfill_knowledge_entries() -> int:
    indexed = 0
    async with AsyncSessionLocal() as db:
        entries = (await db.execute(select(KnowledgeEntry).order_by(KnowledgeEntry.id.asc()))).scalars().all()
    logger.info('Найдено записей KnowledgeEntry: %s', len(entries))

    for entry in entries:
        async with AsyncSessionLocal() as db:
            try:
                await knowledge_service.delete_chunks(
                    db, source_type=knowledge_service.SOURCE_KB, source_id=entry.id
                )
                body = (entry.body or '').strip()
                if not body:
                    continue
                try:
                    tags = json.loads(entry.tags) if entry.tags else []
                except json.JSONDecodeError:
                    tags = []
                await knowledge_service.index_text(
                    db,
                    text=body,
                    source_type=knowledge_service.SOURCE_KB,
                    source_id=entry.id,
                    scope=entry.scope,
                    client_id=entry.client_id,
                    meta={'title': entry.title, 'tags': tags},
                )
                indexed += 1
            except Exception:  # noqa: BLE001
                logger.exception('Не удалось проиндексировать KnowledgeEntry %s', entry.id)
    return indexed


async def main() -> None:
    chats = await backfill_chat_messages()
    kb = await backfill_knowledge_entries()
    logger.info('Готово. Сообщения: %s, KnowledgeEntry: %s', chats, kb)


if __name__ == '__main__':
    asyncio.run(main())
