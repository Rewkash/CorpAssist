"""Семантический кэш ответов LLM на основе эмбеддингов."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.embeddings import embeddings_service
from app.models import SemanticCacheEntry

logger = logging.getLogger(__name__)


async def lookup(
    db: AsyncSession,
    *,
    mode: str,
    query: str,
    scope_key: str = 'global',
    threshold: float | None = None,
) -> Any | None:
    """Возвращает ранее закэшированный ответ, если найдена похожая запись."""
    if not settings.semantic_cache_enabled:
        return None
    cleaned = (query or '').strip()
    if not cleaned:
        return None
    try:
        query_vec = await embeddings_service.embed(cleaned)
    except Exception as exc:  # noqa: BLE001
        logger.warning('Семантический кэш: эмбеддинг запроса не получен: %s', exc)
        return None

    ttl = timedelta(seconds=settings.semantic_cache_ttl_seconds)
    fresh_after = datetime.now(timezone.utc) - ttl
    distance = SemanticCacheEntry.query_embedding.cosine_distance(query_vec)
    stmt = (
        select(SemanticCacheEntry, distance.label('distance'))
        .where(
            and_(
                SemanticCacheEntry.mode == mode,
                SemanticCacheEntry.scope_key == scope_key,
                SemanticCacheEntry.created_at >= fresh_after,
            )
        )
        .order_by(distance.asc())
        .limit(1)
    )
    row = (await db.execute(stmt)).first()
    if not row:
        return None
    entry, dist = row
    score = 1.0 - float(dist)
    limit = threshold if threshold is not None else settings.semantic_cache_threshold
    if score < limit:
        return None
    entry.hit_count = (entry.hit_count or 0) + 1
    entry.last_hit_at = datetime.now(timezone.utc)
    await db.commit()
    try:
        return json.loads(entry.response_json)
    except json.JSONDecodeError:
        logger.warning('Семантический кэш: повреждённый JSON, отбрасываю запись %s', entry.id)
        return None


async def store(
    db: AsyncSession,
    *,
    mode: str,
    query: str,
    response: Any,
    scope_key: str = 'global',
) -> None:
    """Сохраняет ответ в семантический кэш."""
    if not settings.semantic_cache_enabled:
        return
    cleaned = (query or '').strip()
    if not cleaned:
        return
    try:
        query_vec = await embeddings_service.embed(cleaned)
    except Exception as exc:  # noqa: BLE001
        logger.warning('Семантический кэш: эмбеддинг для сохранения не получен: %s', exc)
        return
    try:
        payload = json.dumps(response, ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        logger.warning('Семантический кэш: не сериализовать ответ: %s', exc)
        return
    entry = SemanticCacheEntry(
        mode=mode,
        query_text=cleaned[:4000],
        query_embedding=query_vec,
        response_json=payload,
        scope_key=scope_key,
    )
    db.add(entry)
    await db.commit()
