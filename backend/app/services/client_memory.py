"""Client long-term memory: retrieve profile + conversation summaries for AI context.

Configurable retrieval strategies for evaluation:
  'none'         → no memory (baseline for comparison)
  'recent'       → only last N summaries (no search)
  'topic'        → recent + topic-match
  'hybrid'       → recent + topic + vector + RRF
  'hybrid_decay' → recent + hybrid + temporal decay

Search metrics are logged to rag_search_logs for evaluation pipeline.
"""

import logging
from collections import Counter

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.ollama_client import OllamaClient
from app.models import ClientProfile, ConversationSummary, RAGSearchLog
from app.services.hybrid_search import (
    hybrid_search,
    SearchMetrics,
    SearchTimer,
)
from app.services.embedding_service import embed_query

logger = logging.getLogger(__name__)

# Limits to keep token usage under control
MAX_RECENT_SUMMARIES = 2
MAX_RELEVANT_SUMMARIES = 2
MAX_PROFILE_CHARS = 500
MAX_SUMMARY_CHARS = 300
MAX_TOTAL_MEMORY_CHARS = 1500

# Default strategy — used in production, can be overridden for evaluation
DEFAULT_STRATEGY = 'hybrid'


async def get_client_profile(db: AsyncSession, client_id: int) -> ClientProfile | None:
    result = await db.execute(select(ClientProfile).where(ClientProfile.client_id == client_id))
    return result.scalar_one_or_none()


async def get_recent_summaries(db: AsyncSession, client_id: int, limit: int = MAX_RECENT_SUMMARIES) -> list[ConversationSummary]:
    result = await db.execute(
        select(ConversationSummary)
        .where(ConversationSummary.client_id == client_id)
        .order_by(ConversationSummary.generated_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_or_create_client_profile(db: AsyncSession, client_id: int) -> ClientProfile:
    profile = await get_client_profile(db, client_id)
    if profile:
        return profile
    profile = ClientProfile(client_id=client_id)
    db.add(profile)
    await db.flush()
    return profile


def _format_summary(sm: ConversationSummary) -> str:
    """Format a single conversation summary for inclusion in LLM context."""
    topics = sm.get_key_topics()
    topics_str = f' [{", ".join(topics[:3])}]' if topics else ''
    resolution_str = f' → {sm.resolution}' if sm.resolution else ''
    return f'• {sm.summary[:MAX_SUMMARY_CHARS]}{topics_str}{resolution_str}'


async def _log_search_metrics(db: AsyncSession, metrics: SearchMetrics, conversation_id: int | None = None) -> None:
    """Persist search metrics to database for evaluation pipeline."""
    import json as _json
    log_entry = RAGSearchLog(
        client_id=metrics.client_id,
        conversation_id=conversation_id,
        current_topics=_json.dumps(metrics.current_topics, ensure_ascii=False),
        strategy=metrics.strategy,
        results_count=metrics.results_count,
        topic_hits=metrics.topic_hits,
        vector_hits=metrics.vector_hits,
        rrf_scores=_json.dumps(metrics.rrf_scores),
        hit_summary_ids=_json.dumps(metrics.hit_summary_ids),
        latency_ms=metrics.latency_ms,
    )
    db.add(log_entry)
    try:
        await db.flush()
    except Exception:
        logger.debug('Failed to log search metrics (non-critical)')


async def build_client_memory_context(
    db: AsyncSession,
    client_id: int,
    current_topics: list[str] | None = None,
    llm: OllamaClient | None = None,
    conversation_id: int | None = None,
    strategy: str = DEFAULT_STRATEGY,
) -> str:
    """Build a compact text block with client long-term memory for LLM injection.

    The `strategy` parameter controls which retrieval approach is used:
    - 'none'         → returns empty string (no memory context)
    - 'recent'       → only last N summaries (no search)
    - 'topic'        → recent + topic-match relevant
    - 'hybrid'       → recent + topic + vector + RRF
    - 'hybrid_decay' → recent + hybrid + temporal decay

    Structure (when strategy != 'none'):
      0. Client profile (always included)
      1. Recent conversation summaries (fresh history, always included)
      2. Relevant summaries via hybrid search
    """
    # Strategy: none → empty memory context
    if strategy == 'none':
        return ''

    parts: list[str] = []

    # 0. Client profile (always included unless strategy='none')
    profile = await get_client_profile(db, client_id)
    if profile and profile.profile.strip():
        style_note = ''
        if profile.communication_style:
            style_note = f' Стиль общения: {profile.communication_style}.'
        topics = profile.get_common_topics()
        topics_note = ''
        if topics:
            topics_note = f' Частые темы: {", ".join(topics[:5])}.'
        profile_block = f'📋 Профиль клиента (из {profile.interaction_count} обращений):{style_note}{topics_note}\n{profile.profile[:MAX_PROFILE_CHARS]}'
        parts.append(profile_block)

    # 1. Recent summaries (always included for all non-none strategies)
    recent = await get_recent_summaries(db, client_id, limit=MAX_RECENT_SUMMARIES)
    recent_ids = {sm.id for sm in recent}

    # 2. Relevant summaries via search (depends on strategy)
    relevant_results: list = []
    metrics = SearchMetrics(client_id=client_id, current_topics=current_topics or [], strategy=strategy)

    if strategy in ('topic', 'hybrid', 'hybrid_decay'):
        current_topics = current_topics or []

        # Try to generate query embedding for vector search
        query_embedding: list[float] = []
        if strategy in ('hybrid', 'hybrid_decay') and llm and current_topics:
            try:
                query_text = ' '.join(current_topics)
                query_embedding = await embed_query(llm, query_text)
            except Exception:
                logger.debug('Query embedding generation failed')

        # Run hybrid search with specified strategy
        with SearchTimer() as timer:
            relevant_results, metrics = await hybrid_search(
                db=db,
                client_id=client_id,
                current_topics=current_topics,
                query_embedding=query_embedding,
                exclude_ids=recent_ids,
                max_results=MAX_RELEVANT_SUMMARIES,
                strategy=strategy,
            )
        metrics.latency_ms = timer.elapsed_ms
        metrics.conversation_id = conversation_id

        # Log search metrics for evaluation pipeline
        try:
            await _log_search_metrics(db, metrics, conversation_id)
        except Exception:
            logger.debug('Search metrics logging failed (non-critical)')

    relevant_summaries = [r.summary for r in relevant_results]

    # Combine summaries section
    all_summaries = list(recent) + relevant_summaries
    if all_summaries:
        seen_ids: set[int] = set()
        recent_lines: list[str] = []
        relevant_lines: list[str] = []

        for sm in recent:
            if sm.id in seen_ids:
                continue
            seen_ids.add(sm.id)
            recent_lines.append(_format_summary(sm))

        for r in relevant_results:
            if r.summary.id in seen_ids:
                continue
            seen_ids.add(r.summary.id)
            line = _format_summary(r.summary)
            relevant_lines.append(line)

        summary_parts: list[str] = []
        if recent_lines:
            summary_parts.append('📂 Последние обращения:\n' + '\n'.join(recent_lines))
        if relevant_lines:
            summary_parts.append('🔗 Релевантные прошлые обращения:\n' + '\n'.join(relevant_lines))

        if summary_parts:
            parts.append('\n\n'.join(summary_parts))

    if not parts:
        return ''

    full = '\n\n'.join(parts)
    if len(full) > MAX_TOTAL_MEMORY_CHARS:
        full = full[:MAX_TOTAL_MEMORY_CHARS] + '...'
    return full


async def update_client_profile_from_summary(db: AsyncSession, client_id: int, new_summary: ConversationSummary) -> None:
    """Update client profile after a new conversation summary is generated.

    Merges key topics, updates interaction count, and refreshes the profile text.
    """
    profile = await get_or_create_client_profile(db, client_id)

    existing_topics = profile.get_common_topics()
    new_topics = new_summary.get_key_topics()
    topic_counter = Counter(existing_topics)
    for t in new_topics:
        topic_counter[t] += 1
    top_topics = [t for t, _ in topic_counter.most_common(10)]
    profile.set_common_topics(top_topics)

    profile.interaction_count += 1

    if new_summary.sentiment_trend and not profile.communication_style:
        profile.communication_style = new_summary.sentiment_trend

    new_info = new_summary.summary[:200]
    if profile.profile:
        profile.profile = f'{profile.profile[:400]}\n\nПоследнее обращение: {new_info}'
    else:
        profile.profile = f'Первое обращение: {new_info}'

    if len(profile.profile) > MAX_PROFILE_CHARS * 2:
        profile.profile = profile.profile[:MAX_PROFILE_CHARS * 2] + '...'

    await db.flush()
    logger.info('Client profile updated for client_id=%d (interaction_count=%d)', client_id, profile.interaction_count)
