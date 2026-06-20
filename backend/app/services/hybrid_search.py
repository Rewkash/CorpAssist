"""Hybrid search for client long-term memory: topic-match + vector search + RRF + Decay.

Architecture:
  Channel 1: Topic-match (key_topics overlap with current topics)
  Channel 2: Vector search (cosine similarity via pgvector)
  Fusion: Reciprocal Rank Fusion (RRF) combines ranked results from both channels
  Decay: Temporal relevance multiplier — recent summaries ranked higher

Strategies (controlled by `strategy` parameter):
  'none'         → returns empty results (no memory context)
  'recent'       → returns only recent N summaries (no search)
  'topic'        → topic-match only
  'hybrid'       → topic + vector + RRF
  'hybrid_decay' → hybrid + exponential time decay

Graceful degradation:
  - If pgvector/embeddings unavailable → topic-match only
  - If topic-match finds no matches → vector search only
  - If both available → hybrid RRF (with optional decay)
"""

import logging
import math
import time as _time
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select, text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ConversationSummary, _HAS_PGVECTOR

logger = logging.getLogger(__name__)


def is_pgvector_available() -> bool:
    """Check if pgvector Python package is installed."""
    return _HAS_PGVECTOR


# RRF constant (standard value from IR literature)
RRF_K = 60

# Temporal decay constant: half-life in days
# Summary from 90 days ago gets 50% weight reduction
DECAY_HALF_LIFE_DAYS = 90.0

# Search limits
MAX_TOPIC_RESULTS = 4
MAX_VECTOR_RESULTS = 4
MAX_HYBRID_RESULTS = 4


@dataclass
class SearchMetrics:
    """Metrics collected during a single RAG search act."""
    client_id: int
    conversation_id: int | None = None
    current_topics: list[str] = field(default_factory=list)
    strategy: str = 'hybrid'
    results_count: int = 0
    topic_hits: int = 0
    vector_hits: int = 0
    rrf_scores: list[float] = field(default_factory=list)
    hit_summary_ids: list[int] = field(default_factory=list)
    latency_ms: int = 0

    # Breakdown: which results came from which channel
    topic_only_count: int = 0
    vector_only_count: int = 0
    both_channels_count: int = 0


@dataclass
class SearchResult:
    """A single search result with RRF score."""
    summary: ConversationSummary
    score: float
    source: str  # 'topic', 'vector', 'topic+vector', or 'hybrid_decay'
    decay_factor: float = 1.0  # 1.0 = no decay


class SearchTimer:
    """Context manager to measure search latency."""

    def __init__(self) -> None:
        self.start: float = 0.0
        self.elapsed_ms: int = 0

    def __enter__(self) -> 'SearchTimer':
        self.start = _time.perf_counter()
        return self

    def __exit__(self, *args: object) -> None:
        self.elapsed_ms = int((_time.perf_counter() - self.start) * 1000)


def compute_decay_factor(generated_at: datetime, now: datetime | None = None) -> float:
    """Compute temporal decay factor for a summary based on its age.

    Formula: decay = exp(-alpha * days_old)
    where alpha = ln(2) / half_life_days

    This means:
    - Fresh summary (0 days): decay = 1.0
    - Summary from half_life (90 days): decay = 0.5
    - Summary from 1 year: decay ≈ 0.19
    - Summary from 2 years: decay ≈ 0.03

    Args:
        generated_at: when the summary was created
        now: current time (defaults to utcnow)

    Returns:
        Float between 0 and 1.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    # Handle naive datetimes
    gen_at = generated_at
    if gen_at.tzinfo is None:
        gen_at = gen_at.replace(tzinfo=timezone.utc)

    delta = (now - gen_at).total_seconds()
    days_old = max(0.0, delta / 86400.0)

    alpha = math.log(2) / DECAY_HALF_LIFE_DAYS
    return math.exp(-alpha * days_old)


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
    apply_decay: bool = False,
) -> list[SearchResult]:
    """Combine topic-match and vector search results using RRF.

    RRF formula: score(d) = Σ 1/(k + rank_i(d))
    where k=60 is a standard tuning parameter.

    If apply_decay=True, final score is multiplied by temporal decay factor:
    adjusted_score(d) = rrf_score(d) × decay_factor(d)

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

    # Apply temporal decay if requested
    if apply_decay:
        for sid in scores:
            sm = summaries[sid]
            decay = compute_decay_factor(sm.generated_at)
            scores[sid] *= decay

    # Sort by combined score
    sorted_ids = sorted(scores.keys(), key=lambda sid: scores[sid], reverse=True)

    results: list[SearchResult] = []
    for sid in sorted_ids[:max_results]:
        sm = summaries[sid]
        source = '+'.join(sorted(sources[sid]))
        if apply_decay:
            source = f'{source}_decay'
        decay = compute_decay_factor(sm.generated_at) if apply_decay else 1.0
        results.append(SearchResult(
            summary=sm,
            score=scores[sid],
            source=source,
            decay_factor=round(decay, 4),
        ))

    return results


async def hybrid_search(
    db: AsyncSession,
    client_id: int,
    current_topics: list[str],
    query_embedding: list[float] | None = None,
    exclude_ids: set[int] | None = None,
    max_results: int = MAX_HYBRID_RESULTS,
    strategy: str = 'hybrid',
) -> tuple[list[SearchResult], SearchMetrics]:
    """Perform hybrid search combining topic-match and vector search.

    The `strategy` parameter controls which channels to use:
    - 'none'         → no memory context (empty results)
    - 'recent'       → no search (handled by caller, returns empty)
    - 'topic'        → topic-match only
    - 'hybrid'       → topic + vector + RRF
    - 'hybrid_decay' → hybrid + temporal decay

    Returns (search_results, metrics) tuple for logging.
    """
    metrics = SearchMetrics(
        client_id=client_id,
        current_topics=current_topics,
        strategy=strategy,
    )

    # Strategy: none → empty results
    if strategy == 'none':
        return [], metrics

    # Strategy: recent → no search, caller handles recent-only
    if strategy == 'recent':
        return [], metrics

    # Determine if we should use decay
    apply_decay = strategy == 'hybrid_decay'

    # Channel 1: Topic-match (used for 'topic', 'hybrid', 'hybrid_decay')
    topic_results: list[tuple[ConversationSummary, int]] = []
    use_topic = strategy in ('topic', 'hybrid', 'hybrid_decay')
    if use_topic and current_topics:
        topic_results = await _topic_match(db, client_id, current_topics, exclude_ids)

    # Channel 2: Vector search (used for 'hybrid', 'hybrid_decay')
    vector_results: list[tuple[ConversationSummary, float]] = []
    use_vector = strategy in ('hybrid', 'hybrid_decay')
    if use_vector and query_embedding and _HAS_PGVECTOR:
        vector_results = await _vector_search(db, client_id, query_embedding, exclude_ids)

    # Populate metrics
    metrics.topic_hits = len(topic_results)
    metrics.vector_hits = len(vector_results)

    # Fusion
    results: list[SearchResult] = []
    if topic_results and vector_results:
        # Both channels available → RRF (with optional decay)
        results = _reciprocal_rank_fusion(topic_results, vector_results, max_results, apply_decay)
        metrics.both_channels_count = len([r for r in results if 'topic' in r.source and 'vector' in r.source])
        metrics.topic_only_count = len([r for r in results if 'topic' in r.source and 'vector' not in r.source.replace('_decay', '')])
        metrics.vector_only_count = len([r for r in results if 'vector' in r.source and 'topic' not in r.source])
    elif topic_results:
        # Topic-match only → simple ranking by overlap count
        seen: set[int] = set()
        for sm, overlap in topic_results[:max_results]:
            if sm.id not in seen:
                seen.add(sm.id)
                decay = compute_decay_factor(sm.generated_at) if apply_decay else 1.0
                score = overlap * decay if apply_decay else overlap
                source = 'topic_decay' if apply_decay else 'topic'
                results.append(SearchResult(summary=sm, score=score, source=source, decay_factor=round(decay, 4)))
        metrics.topic_only_count = len(results)
    elif vector_results:
        # Vector search only → ranked by similarity
        seen: set[int] = set()
        for sm, similarity in vector_results[:max_results]:
            if sm.id not in seen:
                seen.add(sm.id)
                decay = compute_decay_factor(sm.generated_at) if apply_decay else 1.0
                score = similarity * decay if apply_decay else similarity
                source = 'vector_decay' if apply_decay else 'vector'
                results.append(SearchResult(summary=sm, score=score, source=source, decay_factor=round(decay, 4)))
        metrics.vector_only_count = len(results)

    # Finalize metrics
    metrics.results_count = len(results)
    metrics.rrf_scores = [round(r.score, 6) for r in results]
    metrics.hit_summary_ids = [r.summary.id for r in results]

    return results, metrics
