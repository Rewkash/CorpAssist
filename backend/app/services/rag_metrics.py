"""RAG search metrics: aggregation and evaluation queries.

Provides aggregation endpoints for building comparison tables
and charts suitable for thesis evaluation chapter.
"""

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RAGSearchLog, EvaluationLog

logger = logging.getLogger(__name__)


# Memory strategy constants
STRATEGY_NONE = 'none'
STRATEGY_RECENT = 'recent'
STRATEGY_TOPIC = 'topic'
STRATEGY_HYBRID = 'hybrid'
STRATEGY_HYBRID_DECAY = 'hybrid_decay'

ALL_STRATEGIES = [STRATEGY_NONE, STRATEGY_RECENT, STRATEGY_TOPIC, STRATEGY_HYBRID, STRATEGY_HYBRID_DECAY]


async def get_rag_summary(
    db: AsyncSession,
    strategy: str | None = None,
) -> dict[str, Any]:
    """Aggregate RAG search statistics, optionally filtered by strategy.

    Returns hit_rate, avg_results, avg_latency, channel_distribution.
    """
    base_query = select(RAGSearchLog)
    if strategy:
        base_query = base_query.where(RAGSearchLog.strategy == strategy)

    result = await db.execute(base_query)
    logs = result.scalars().all()

    if not logs:
        return {
            'strategy': strategy or 'all',
            'total_searches': 0,
            'hit_rate': 0.0,
            'avg_results': 0.0,
            'avg_latency_ms': 0.0,
            'topic_only_pct': 0.0,
            'vector_only_pct': 0.0,
            'hybrid_pct': 0.0,
            'no_hits_pct': 0.0,
        }

    total = len(logs)
    hits = sum(1 for l in logs if l.results_count > 0)
    topic_only = sum(1 for l in logs if l.topic_hits > 0 and l.vector_hits == 0)
    vector_only = sum(1 for l in logs if l.vector_hits > 0 and l.topic_hits == 0)
    hybrid = sum(1 for l in logs if l.topic_hits > 0 and l.vector_hits > 0)
    no_hits = sum(1 for l in logs if l.results_count == 0)

    return {
        'strategy': strategy or 'all',
        'total_searches': total,
        'hit_rate': round(hits / total, 3) if total else 0.0,
        'avg_results': round(sum(l.results_count for l in logs) / total, 2) if total else 0.0,
        'avg_latency_ms': round(sum(l.latency_ms for l in logs) / total, 1) if total else 0.0,
        'topic_only_pct': round(topic_only / total, 3) if total else 0.0,
        'vector_only_pct': round(vector_only / total, 3) if total else 0.0,
        'hybrid_pct': round(hybrid / total, 3) if total else 0.0,
        'no_hits_pct': round(no_hits / total, 3) if total else 0.0,
    }


async def get_rag_comparison(db: AsyncSession) -> list[dict[str, Any]]:
    """Get RAG metrics comparison across all strategies.

    Returns a list of summary dicts, one per strategy.
    Used for building comparison tables for the thesis.
    """
    results = []
    for strat in ALL_STRATEGIES:
        summary = await get_rag_summary(db, strategy=strat)
        results.append(summary)
    return results


async def get_eval_summary(
    db: AsyncSession,
    strategy: str | None = None,
) -> dict[str, Any]:
    """Aggregate evaluation scores, optionally filtered by strategy."""
    from app.models import EvaluationLog

    base_query = select(EvaluationLog)
    if strategy:
        base_query = base_query.where(EvaluationLog.strategy == strategy)

    result = await db.execute(base_query)
    evals = result.scalars().all()

    if not evals:
        return {
            'strategy': strategy or 'all',
            'total_evaluations': 0,
            'avg_relevance': 0.0,
            'avg_politeness': 0.0,
            'avg_completeness': 0.0,
            'avg_accuracy': 0.0,
            'avg_overall': 0.0,
        }

    total = len(evals)
    return {
        'strategy': strategy or 'all',
        'total_evaluations': total,
        'avg_relevance': round(sum(e.relevance for e in evals) / total, 2),
        'avg_politeness': round(sum(e.politeness for e in evals) / total, 2),
        'avg_completeness': round(sum(e.completeness for e in evals) / total, 2),
        'avg_accuracy': round(sum(e.accuracy for e in evals) / total, 2),
        'avg_overall': round(sum(e.overall for e in evals) / total, 2),
    }


async def get_eval_comparison(db: AsyncSession) -> list[dict[str, Any]]:
    """Get evaluation comparison across all strategies.

    Returns list of evaluation summary dicts for building
    comparison tables suitable for thesis tables and charts.
    """
    results = []
    for strat in ALL_STRATEGIES:
        summary = await get_eval_summary(db, strategy=strat)
        results.append(summary)
    return results


async def get_full_comparison(db: AsyncSession) -> dict[str, list[dict[str, Any]]]:
    """Combined RAG + evaluation comparison for all strategies.

    This is the primary endpoint for generating thesis data:
    one row per strategy, with both search metrics and quality scores.
    """
    rag_data = await get_rag_comparison(db)
    eval_data = await get_eval_comparison(db)

    # Merge by strategy
    eval_by_strategy = {e['strategy']: e for e in eval_data}

    merged = []
    for rag in rag_data:
        strat = rag['strategy']
        ev = eval_by_strategy.get(strat, {})
        merged.append({
            **rag,
            'total_evaluations': ev.get('total_evaluations', 0),
            'avg_relevance': ev.get('avg_relevance', 0.0),
            'avg_politeness': ev.get('avg_politeness', 0.0),
            'avg_completeness': ev.get('avg_completeness', 0.0),
            'avg_accuracy': ev.get('avg_accuracy', 0.0),
            'avg_overall': ev.get('avg_overall', 0.0),
        })

    return {'strategies': merged}
