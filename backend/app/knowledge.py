"""RAG: индексация знаний, поиск похожих кусочков, сборка блока для промпта."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.embeddings import embeddings_service
from app.models import KnowledgeChunk

logger = logging.getLogger(__name__)


SOURCE_CHAT = 'chat'
SOURCE_KB = 'kb'
SOURCE_SUMMARY = 'summary'

SCOPE_GLOBAL = 'global'
SCOPE_CLIENT = 'client'


@dataclass
class KnowledgeHit:
    chunk_id: int
    text: str
    score: float
    source_type: str
    source_id: int | None
    scope: str
    client_id: int | None
    meta: dict


def split_into_chunks(text: str, max_chars: int | None = None) -> list[str]:
    """Аккуратное разбиение длинного текста на куски по абзацам/предложениям."""
    limit = max_chars or settings.rag_max_chars_per_chunk
    cleaned = (text or '').strip()
    if not cleaned:
        return []
    if len(cleaned) <= limit:
        return [cleaned]

    paragraphs = [p.strip() for p in re.split(r'\n{2,}', cleaned) if p.strip()]
    chunks: list[str] = []
    buffer = ''
    for paragraph in paragraphs:
        if len(paragraph) > limit:
            sentences = re.split(r'(?<=[.!?])\s+', paragraph)
            for sentence in sentences:
                if not sentence:
                    continue
                if len(buffer) + len(sentence) + 1 > limit:
                    if buffer:
                        chunks.append(buffer.strip())
                    buffer = sentence
                else:
                    buffer = f'{buffer} {sentence}'.strip()
            continue
        if len(buffer) + len(paragraph) + 2 > limit:
            if buffer:
                chunks.append(buffer.strip())
            buffer = paragraph
        else:
            buffer = f'{buffer}\n\n{paragraph}'.strip() if buffer else paragraph
    if buffer.strip():
        chunks.append(buffer.strip())
    return chunks


async def index_text(
    db: AsyncSession,
    *,
    text: str,
    source_type: str,
    source_id: int | None,
    scope: str = SCOPE_GLOBAL,
    client_id: int | None = None,
    meta: dict | None = None,
) -> list[KnowledgeChunk]:
    """Разбивает текст на куски, считает эмбеддинги и сохраняет в knowledge_chunks."""
    pieces = split_into_chunks(text)
    if not pieces:
        return []

    saved: list[KnowledgeChunk] = []
    for piece in pieces:
        try:
            vector = await embeddings_service.embed(piece)
        except Exception as exc:  # noqa: BLE001
            logger.warning('Не удалось получить эмбеддинг для chunk: %s', exc)
            continue
        chunk = KnowledgeChunk(
            source_type=source_type,
            source_id=source_id,
            scope=scope,
            client_id=client_id,
            text=piece,
            embedding=vector,
            chunk_meta=meta or {},
        )
        db.add(chunk)
        saved.append(chunk)
    if saved:
        await db.commit()
        for chunk in saved:
            await db.refresh(chunk)
    return saved


async def delete_chunks(
    db: AsyncSession,
    *,
    source_type: str,
    source_id: int,
) -> int:
    """Удаляет все куски конкретного источника (например, при пересохранении KnowledgeEntry)."""
    result = await db.execute(
        select(KnowledgeChunk).where(
            and_(KnowledgeChunk.source_type == source_type, KnowledgeChunk.source_id == source_id)
        )
    )
    chunks = list(result.scalars().all())
    for chunk in chunks:
        await db.delete(chunk)
    if chunks:
        await db.commit()
    return len(chunks)


async def search(
    db: AsyncSession,
    *,
    query: str,
    client_id: int | None,
    top_k: int | None = None,
    min_score: float | None = None,
    source_types: list[str] | None = None,
) -> list[KnowledgeHit]:
    """Семантический поиск по knowledge_chunks с фильтром по scope/клиенту."""
    if not query.strip():
        return []
    try:
        query_vec = await embeddings_service.embed(query)
    except Exception as exc:  # noqa: BLE001
        logger.warning('RAG: эмбеддинг запроса не получен: %s', exc)
        return []

    k = top_k or settings.rag_top_k
    threshold = min_score if min_score is not None else settings.rag_min_score

    distance = KnowledgeChunk.embedding.cosine_distance(query_vec)
    scope_filter = KnowledgeChunk.scope == SCOPE_GLOBAL
    if client_id is not None:
        scope_filter = or_(
            scope_filter,
            and_(KnowledgeChunk.scope == SCOPE_CLIENT, KnowledgeChunk.client_id == client_id),
        )

    stmt = (
        select(KnowledgeChunk, distance.label('distance'))
        .where(scope_filter)
        .order_by(distance.asc())
        .limit(k)
    )
    if source_types:
        stmt = stmt.where(KnowledgeChunk.source_type.in_(source_types))

    rows = (await db.execute(stmt)).all()
    hits: list[KnowledgeHit] = []
    for chunk, dist in rows:
        score = 1.0 - float(dist)
        if score < threshold:
            continue
        hits.append(
            KnowledgeHit(
                chunk_id=chunk.id,
                text=chunk.text,
                score=score,
                source_type=chunk.source_type,
                source_id=chunk.source_id,
                scope=chunk.scope,
                client_id=chunk.client_id,
                meta=chunk.chunk_meta or {},
            )
        )
    return hits


def build_prompt_block(hits: list[KnowledgeHit], header: str | None = None) -> str:
    """Форматирует найденные куски в системный блок «известных фактов»."""
    if not hits:
        return ''
    title = header or 'Известные факты из базы знаний компании'
    lines: list[str] = [f'### {title}']
    for idx, hit in enumerate(hits, start=1):
        prefix = {
            SOURCE_KB: 'Регламент',
            SOURCE_CHAT: 'Из переписки',
            SOURCE_SUMMARY: 'Профиль клиента',
        }.get(hit.source_type, 'Источник')
        snippet = hit.text.strip().replace('\n', ' ')
        if len(snippet) > 600:
            snippet = snippet[:600].rstrip() + '...'
        lines.append(f'[{idx}] {prefix}: {snippet}')
    lines.append('Используй эти факты, если они относятся к запросу. Не выдумывай того, чего нет.')
    return '\n'.join(lines)
