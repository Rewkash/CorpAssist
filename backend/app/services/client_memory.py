"""Client long-term memory: retrieve profile + conversation summaries for AI context."""

import logging
from collections import Counter

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ClientProfile, ConversationSummary

logger = logging.getLogger(__name__)

# Limits to keep token usage under control
MAX_SUMMARIES = 3
MAX_PROFILE_CHARS = 500
MAX_SUMMARY_CHARS = 300
MAX_TOTAL_MEMORY_CHARS = 1500


async def get_client_profile(db: AsyncSession, client_id: int) -> ClientProfile | None:
    result = await db.execute(select(ClientProfile).where(ClientProfile.client_id == client_id))
    return result.scalar_one_or_none()


async def get_recent_summaries(db: AsyncSession, client_id: int, limit: int = MAX_SUMMARIES) -> list[ConversationSummary]:
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


async def build_client_memory_context(db: AsyncSession, client_id: int) -> str:
    """Build a compact text block with client long-term memory for LLM injection.

    Structure:
      1. Client profile (communication style, common topics)
      2. Recent conversation summaries (key facts, resolutions)

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

    # 2. Conversation summaries
    summaries = await get_recent_summaries(db, client_id)
    if summaries:
        summary_lines: list[str] = []
        for sm in reversed(summaries):  # chronological order
            topics = sm.get_key_topics()
            topics_str = f' [{", ".join(topics[:3])}]' if topics else ''
            resolution_str = f' → {sm.resolution}' if sm.resolution else ''
            line = f'• {sm.summary[:MAX_SUMMARY_CHARS]}{topics_str}{resolution_str}'
            summary_lines.append(line)
        summaries_block = '📂 Предыдущие обращения:\n' + '\n'.join(summary_lines)
        parts.append(summaries_block)

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
