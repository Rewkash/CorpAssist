"""Hybrid search for client long-term memory: topic-match + vector search + RRF.

Architecture:
  Channel 1: Topic-match (key_topics overlap with current topics)
  Channel 2: Vector search (cosine similarity via pgvector)
  Fusion: Reciprocal Rank Fusion (RRF) combines ranked results from both channels

Graceful degradation:
  - If pgvector/embeddings unavailable → topic-match only
  - If topic-match finds no matches → vector search only
  - If both available → hybrid RRF
"""

import logging
from dataclasses import dataclass

from sqlalchemy import select, text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ConversationSummary, _HAS_PGVECTOR

logger = logging.getLogger(__name__)


def is_pgvector_available() -> bool:
    """Check if pgvector Python package is installed."""
    return _HAS_PGVECTOR

# RRF constant (standard value from IR literature)
RRF_K = 60

# Search limits
MAX_TOPIC_RESULTS = 4
MAX_VECTOR_RESULTS = 4
MAX_HYBRID_RESULTS = 4


@dataclass
class SearchResult:
    """A single search result with RRF score."""
    summary: ConversationSummary
    score: float
    source: str  # 'topic', 'vector', or 'hybrid'


async def _topic_match(
    db: AsyncSession,
    client_id: int,
    current_topics: list[str],
    exclude_ids: set[int] | None = None,
    limit: int = MAX_TOPIC_RESULTS,
) -> list[tuple[ConversationSummary, int]]:
    """Find summaries whose key_topics overlap with current topics.

    Returns list of (summary, overlap_count) sorted by overlap desc.
    """
    if not current_topics:
        return []

    exclude_ids = exclude_ids or set()
    current_topics_lower = {t.lower().strip() for t in current_topics if t.strip()}
    if not current_topics_lower:
        return []

    result = await db.execute(
        select(ConversationSummary)
        .where(ConversationSummary.client_id == client_id)
        .order_by(ConversationSummary.generated_at.desc())
    )
    all_summaries = list(result.scalars().all())

    scored: list[tuple[ConversationSummary, int]] = []
    for sm in all_summaries:
        if sm.id in exclude_ids:
            continue
        sm_topics_lower = {t.lower().strip() for t in sm.get_key_topics() if t.strip()}
        overlap = len(current_topics_lower & sm_topics_lower)
        if overlap > 0:
            scored.append((sm, overlap))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:limit]


async def _vector_search(
    db: AsyncSession,
    client_id: int,
    query_embedding: list[float],
    exclude_ids: set[int] | None = None,
    limit: int = MAX_VECTOR_RESULTS,
) -> list[tuple[ConversationSummary, float]]:
    """Find summaries by cosine similarity to query embedding.

    Returns list of (summary, similarity) sorted by similarity desc.
    Returns empty list if pgvector is not available or no embeddings stored.
    """
    if not _HAS_PGVECTOR or not query_embedding:
        return []

    exclude_ids = exclude_ids or set()

    # Use raw SQL for pgvector cosine distance search
    # Filter by client_id for strict isolation
    exclude_clause = ''
    params: dict = {
        'client_id': client_id,
        'embedding': str(query_embedding),
    }
    if exclude_ids:
        placeholders = ','.join(f':eid{i}' for i in range(len(exclude_ids)))
        exclude_clause = f'AND id NOT IN ({placeholders})'
        for i, eid in enumerate(exclude_ids):
            params[f'eid{i}'] = eid

    query = sa_text(f"""
        SELECT id, conversation_id, client_id, summary, key_topics,
               resolution, sentiment_trend, generated_at,
               1 - (embedding <=> :embedding) AS similarity
        FROM conversation_summaries
        WHERE client_id = :client_id
          AND embedding IS NOT NULL
          {exclude_clause}
        ORDER BY embedding <=> :embedding
        LIMIT :limit
    """)
    params['limit'] = limit

    try:
        result = await db.execute(query, params)
        rows = result.fetchall()
    except Exception:
        logger.exception('Vector search failed for client_id=%d', client_id)
        return []

    # Build ConversationSummary objects from rows
    summaries_with_score: list[tuple[ConversationSummary, float]] = []
    for row in rows:
        sm = ConversationSummary(
            id=row.id,
            conversation_id=row.conversation_id,
            client_id=row.client_id,
            summary=row.summary,
            key_topics=row.key_topics,
            resolution=row.resolution,
            sentiment_trend=row.sentiment_trend,
            generated_at=row.generated_at,
        )
        summaries_with_score.append((sm, float(row.similarity)))

    return summaries_with_score


def _reciprocal_rank_fusion(
    topic_results: list[tuple[ConversationSummary, int]],
    vector_results: list[tuple[ConversationSummary, float]],
    max_results: int = MAX_HYBRID_RESULTS,
) -> list[SearchResult]:
    """Combine topic-match and vector search results using RRF.

    RRF formula: score(d) = Σ 1/(k + rank_i(d))
    where k=60 is a standard tuning parameter.

    Ranks are 1-based (rank 1 = best result).
    """
    # Track scores per summary id
    scores: dict[int, float] = {}
    summaries: dict[int, ConversationSummary] = {}
    sources: dict[int, set[str]] = {}

    # Topic-match rankings (sorted by overlap count desc)
    for rank, (sm, _overlap) in enumerate(topic_results, start=1):
        if sm.id not in scores:
            scores[sm.id] = 0.0
            summaries[sm.id] = sm
            sources[sm.id] = set()
        scores[sm.id] += 1.0 / (RRF_K + rank)
        sources[sm.id].add('topic')

    # Vector search rankings (sorted by similarity desc)
    for rank, (sm, _similarity) in enumerate(vector_results, start=1):
        if sm.id not in scores:
            scores[sm.id] = 0.0
            summaries[sm.id] = sm
            sources[sm.id] = set()
        scores[sm.id] += 1.0 / (RRF_K + rank)
        sources[sm.id].add('vector')

    # Sort by combined RRF score
    sorted_ids = sorted(scores.keys(), key=lambda sid: scores[sid], reverse=True)

    results: list[SearchResult] = []
    for sid in sorted_ids[:max_results]:
        source = '+'.join(sorted(sources[sid]))
        results.append(SearchResult(
            summary=summaries[sid],
            score=scores[sid],
            source=source,
        ))

    return results


async def hybrid_search(
    db: AsyncSession,
    client_id: int,
    current_topics: list[str],
    query_embedding: list[float] | None = None,
    exclude_ids: set[int] | None = None,
    max_results: int = MAX_HYBRID_RESULTS,
) -> list[SearchResult]:
    """Perform hybrid search combining topic-match and vector search.

    Automatically degrades:
    - With embeddings available → full hybrid RRF
    - Without embeddings → topic-match only
    - Without topics → vector search only
    - Without either → empty results
    """
    # Channel 1: Topic-match
    topic_results: list[tuple[ConversationSummary, int]] = []
    if current_topics:
        topic_results = await _topic_match(db, client_id, current_topics, exclude_ids)

    # Channel 2: Vector search
    vector_results: list[tuple[ConversationSummary, float]] = []
    if query_embedding and _HAS_PGVECTOR:
        vector_results = await _vector_search(db, client_id, query_embedding, exclude_ids)

    # Fusion
    if topic_results and vector_results:
        # Both channels available → RRF
        return _reciprocal_rank_fusion(topic_results, vector_results, max_results)
    elif topic_results:
        # Topic-match only → simple ranking by overlap count
        results: list[SearchResult] = []
        seen: set[int] = set()
        for sm, overlap in topic_results[:max_results]:
            if sm.id not in seen:
                seen.add(sm.id)
                results.append(SearchResult(summary=sm, score=overlap, source='topic'))
        return results
    elif vector_results:
        # Vector search only → ranked by similarity
        results = []
        seen: set[int] = set()
        for sm, similarity in vector_results[:max_results]:
            if sm.id not in seen:
                seen.add(sm.id)
                results.append(SearchResult(summary=sm, score=similarity, source='vector'))
        return results
    else:
        return []
