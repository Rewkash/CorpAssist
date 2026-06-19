"""Client long-term memory: retrieve profile + conversation summaries for AI context.

Three-level retrieval strategy:
  0. Client profile (always included — aggregated info)
  1. Recent summaries (fresh history, always included)
  2. Relevant summaries via hybrid search:
     - Channel A: Topic-match (key_topics overlap)
     - Channel B: Vector search (pgvector cosine similarity)
     - Fusion: Reciprocal Rank Fusion (RRF)

Graceful degradation:
  - pgvector available + embeddings stored → hybrid RRF
  - pgvector unavailable / no embeddings → topic-match only
  - No topics match → recent summaries only
"""

import logging
from collections import Counter

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.ollama_client import OllamaClient
from app.models import ClientProfile, ConversationSummary
from app.services.hybrid_search import hybrid_search, is_pgvector_available
from app.services.embedding_service import embed_query

logger = logging.getLogger(__name__)

# Limits to keep token usage under control
MAX_RECENT_SUMMARIES = 2
MAX_RELEVANT_SUMMARIES = 2
MAX_PROFILE_CHARS = 500
MAX_SUMMARY_CHARS = 300
MAX_TOTAL_MEMORY_CHARS = 1500


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


async def build_client_memory_context(
    db: AsyncSession,
    client_id: int,
    current_topics: list[str] | None = None,
    llm: OllamaClient | None = None,
) -> str:
    """Build a compact text block with client long-term memory for LLM injection.

    Structure:
      0. Client profile (always included)
      1. Recent conversation summaries (fresh history, always included)
      2. Relevant summaries via hybrid search (topic + vector with RRF)

    The total size is capped at MAX_TOTAL_MEMORY_CHARS to avoid token bloat.
    """
    parts: list[str] = []

    # 0. Client profile (always included)
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

    # 1. Recent summaries (always included — fresh context)
    recent = await get_recent_summaries(db, client_id, limit=MAX_RECENT_SUMMARIES)
    recent_ids = {sm.id for sm in recent}

    # 2. Relevant summaries via hybrid search
    relevant_results: list = []
    current_topics = current_topics or []

    # Try to generate query embedding for vector search
    query_embedding: list[float] = []
    if llm and current_topics:
        try:
            query_text = ' '.join(current_topics)
            query_embedding = await embed_query(llm, query_text)
        except Exception:
            logger.debug('Query embedding generation failed, falling back to topic-match only')

    # Run hybrid search (automatically degrades to topic-match if no embedding)
    try:
        relevant_results = await hybrid_search(
            db=db,
            client_id=client_id,
            current_topics=current_topics,
            query_embedding=query_embedding,
            exclude_ids=recent_ids,
            max_results=MAX_RELEVANT_SUMMARIES,
        )
    except Exception:
        logger.exception('Hybrid search failed for client_id=%d', client_id)
        relevant_results = []

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
            # Include source info for debug/audit: [topic] [vector] [hybrid]
            source_tag = f' [{r.source}]' if r.source != 'topic' else ''
            line = _format_summary(r.summary) + source_tag
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

    Merges key topics, updates interaction count, and refreshes the profile text
    using a weighted merge (keeps old profile flavor but incorporates new info).
    """
    profile = await get_or_create_client_profile(db, client_id)

    # Merge key topics
    existing_topics = profile.get_common_topics()
    new_topics = new_summary.get_key_topics()
    topic_counter = Counter(existing_topics)
    for t in new_topics:
        topic_counter[t] += 1
    top_topics = [t for t, _ in topic_counter.most_common(10)]
    profile.set_common_topics(top_topics)

    # Update interaction count
    profile.interaction_count += 1

    # Update communication style based on sentiment trend
    if new_summary.sentiment_trend and not profile.communication_style:
        profile.communication_style = new_summary.sentiment_trend

    # Append new summary info to profile, keeping it compact
    new_info = new_summary.summary[:200]
    if profile.profile:
        # Keep last ~400 chars of existing profile + add new info
        profile.profile = f'{profile.profile[:400]}\n\nПоследнее обращение: {new_info}'
    else:
        profile.profile = f'Первое обращение: {new_info}'

    # Keep total profile under limit
    if len(profile.profile) > MAX_PROFILE_CHARS * 2:
        profile.profile = profile.profile[:MAX_PROFILE_CHARS * 2] + '...'

    await db.flush()
    logger.info('Client profile updated for client_id=%d (interaction_count=%d)', client_id, profile.interaction_count)
