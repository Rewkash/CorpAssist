"""Client long-term memory: retrieve profile + conversation summaries for AI context.

Two-level retrieval strategy:
  1. Client profile (always included)
  2. Recent summaries (fresh history)
  3. Topically relevant summaries (topic-match from older dialogs)

This ensures that even old conversations resurface when their topics
overlap with the current dialog, without requiring vector search.
"""

import json as _json
import logging
from collections import Counter

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ClientProfile, ConversationSummary

logger = logging.getLogger(__name__)

# Limits to keep token usage under control
MAX_RECENT_SUMMARIES = 2
MAX_TOPIC_MATCH_SUMMARIES = 2
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


async def get_topic_matched_summaries(
    db: AsyncSession,
    client_id: int,
    current_topics: list[str],
    exclude_ids: set[int] | None = None,
    limit: int = MAX_TOPIC_MATCH_SUMMARIES,
) -> list[ConversationSummary]:
    """Find older conversation summaries whose key_topics overlap with current topics.

    Uses PostgreSQL's JSONB array containment for efficient topic matching.
    Falls back to a simpler approach if JSONB operators aren't available.
    """
    if not current_topics:
        return []

    exclude_ids = exclude_ids or set()

    # Fetch all summaries for this client that aren't already selected
    result = await db.execute(
        select(ConversationSummary)
        .where(ConversationSummary.client_id == client_id)
        .order_by(ConversationSummary.generated_at.desc())
    )
    all_summaries = list(result.scalars().all())

    # Score each summary by topic overlap
    scored: list[tuple[int, ConversationSummary]] = []
    current_topics_lower = {t.lower().strip() for t in current_topics if t.strip()}
    for sm in all_summaries:
        if sm.id in exclude_ids:
            continue
        sm_topics_lower = {t.lower().strip() for t in sm.get_key_topics() if t.strip()}
        overlap = len(current_topics_lower & sm_topics_lower)
        if overlap > 0:
            scored.append((overlap, sm))

    # Sort by overlap count (desc), then by recency (generated_at desc via list order)
    scored.sort(key=lambda x: x[0], reverse=True)

    return [sm for _, sm in scored[:limit]]


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
) -> str:
    """Build a compact text block with client long-term memory for LLM injection.

    Structure:
      1. Client profile (communication style, common topics)
      2. Recent conversation summaries (fresh history, always included)
      3. Topically relevant summaries (matched by key_topics overlap)

    The total size is capped at MAX_TOTAL_MEMORY_CHARS to avoid token bloat.
    """
    parts: list[str] = []

    # 1. Client profile
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

    # 2. Recent summaries (always included)
    recent = await get_recent_summaries(db, client_id, limit=MAX_RECENT_SUMMARIES)
    recent_ids = {sm.id for sm in recent}

    # 3. Topic-matched summaries (from older dialogs)
    topic_matched: list[ConversationSummary] = []
    if current_topics:
        topic_matched = await get_topic_matched_summaries(
            db, client_id, current_topics, exclude_ids=recent_ids,
        )

    # Combine summaries section
    all_summaries = recent + topic_matched
    if all_summaries:
        # Deduplicate and separate by relevance type
        seen_ids: set[int] = set()
        recent_lines: list[str] = []
        relevant_lines: list[str] = []

        for sm in recent:
            if sm.id in seen_ids:
                continue
            seen_ids.add(sm.id)
            recent_lines.append(_format_summary(sm))

        for sm in topic_matched:
            if sm.id in seen_ids:
                continue
            seen_ids.add(sm.id)
            relevant_lines.append(_format_summary(sm))

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
