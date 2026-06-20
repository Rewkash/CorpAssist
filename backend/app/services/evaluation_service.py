"""LLM-as-Judge evaluation service for AI-generated responses.

Evaluates response quality on 4 criteria (relevance, politeness,
completeness, accuracy) using the same LLM that generates responses.

This implements the LLM-as-Judge pattern from the AI evaluation
literature (Zheng et al., 2023; RAGAS framework).
"""

import logging
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.generator import generator_service
from app.models import EvaluationLog, MessageHistory
from app.prompts.llm_prompts import SYSTEM_PROMPT_EVALUATE

logger = logging.getLogger(__name__)


def _parse_evaluation(raw: str) -> dict[str, int]:
    """Parse LLM judge output into evaluation scores."""
    result = {
        'relevance': 0,
        'politeness': 0,
        'completeness': 0,
        'accuracy': 0,
    }

    field_map = {
        'РЕЛЕВАНТНОСТЬ': 'relevance',
        'RELEVANCE': 'relevance',
        'ВЕЖЛИВОСТЬ': 'politeness',
        'POLITENESS': 'politeness',
        'ПОЛНОТА': 'completeness',
        'COMPLETENESS': 'completeness',
        'ТОЧНОСТЬ': 'accuracy',
        'ACCURACY': 'accuracy',
    }

    for line in raw.strip().splitlines():
        line = line.strip()
        for ru_key, en_key in field_map.items():
            if line.upper().startswith(ru_key):
                # Extract number after colon
                match = re.search(r'(\d)', line)
                if match:
                    score = int(match.group(1))
                    result[en_key] = max(1, min(5, score))
                break

    return result


async def evaluate_response(
    db: AsyncSession,
    client_message: str,
    operator_response: str,
    strategy: str = 'none',
    message_history_id: int | None = None,
    context: str = '',
) -> EvaluationLog | None:
    """Evaluate a single operator response using LLM-as-Judge.

    Args:
        db: database session
        client_message: original client message
        operator_response: AI-generated response to evaluate
        strategy: memory strategy used to generate the response
        message_history_id: optional link to MessageHistory record
        context: optional conversation context (for judge reference)

    Returns:
        EvaluationLog record with scores, or None if evaluation failed.
    """
    # Build judge prompt
    context_block = ''
    if context.strip():
        # Truncate context for judge — we don't need full history
        short_ctx = context[:500]
        context_block = f'\nКонтекст диалога (для справки):\n{short_ctx}\n'

    user_prompt = (
        f'Сообщение клиента:\n{client_message[:1000]}\n\n'
        f'Ответ оператора:\n{operator_response[:1000]}\n'
        f'{context_block}'
    )

    model = generator_service._llm.model
    try:
        raw = await generator_service._llm.generate(
            system_prompt=SYSTEM_PROMPT_EVALUATE,
            user_prompt=user_prompt,
            temperature=0.1,
            max_tokens=200,
            mode='evaluate_response',
        )
    except Exception:
        logger.exception('LLM-as-Judge evaluation failed')
        return None

    scores = _parse_evaluation(raw)

    # Check if parsing succeeded (at least some non-zero scores)
    if all(v == 0 for v in scores.values()):
        logger.warning('LLM-as-Judge parsing failed, raw: %s', raw[:200])
        # Try to extract any numbers from the response as fallback
        numbers = re.findall(r'[1-5]', raw)
        if len(numbers) >= 4:
            scores['relevance'] = int(numbers[0])
            scores['politeness'] = int(numbers[1])
            scores['completeness'] = int(numbers[2])
            scores['accuracy'] = int(numbers[3])

    overall = sum(scores.values()) / 4.0 if any(v > 0 for v in scores.values()) else 0.0

    evaluation = EvaluationLog(
        message_history_id=message_history_id,
        strategy=strategy,
        relevance=scores['relevance'],
        politeness=scores['politeness'],
        completeness=scores['completeness'],
        accuracy=scores['accuracy'],
        overall=overall,
        judge_model=model,
        judge_raw=raw[:2000],
    )
    db.add(evaluation)
    await db.commit()

    logger.info(
        'Evaluated response (strategy=%s): R=%d P=%d C=%d A=%d overall=%.1f',
        strategy, scores['relevance'], scores['politeness'],
        scores['completeness'], scores['accuracy'], overall,
    )
    return evaluation


async def evaluate_history_entry(
    db: AsyncSession,
    history: MessageHistory,
    strategy: str = 'none',
    context: str = '',
) -> EvaluationLog | None:
    """Evaluate an existing MessageHistory entry."""
    return await evaluate_response(
        db=db,
        client_message=history.source_text,
        operator_response=history.result_text,
        strategy=strategy,
        message_history_id=history.id,
        context=context,
    )


async def batch_evaluate(
    db: AsyncSession,
    strategy: str = 'none',
    limit: int = 50,
) -> dict[str, Any]:
    """Run LLM-as-Judge evaluation on un-evaluated MessageHistory entries.

    Returns summary statistics.
    """
    # Find MessageHistory entries not yet evaluated for this strategy
    evaluated_ids = select(EvaluationLog.message_history_id).where(
        EvaluationLog.strategy == strategy,
        EvaluationLog.message_history_id.isnot(None),
    )
    result = await db.execute(
        select(MessageHistory)
        .where(
            MessageHistory.mode == 'reply',
            ~MessageHistory.id.in_(evaluated_ids),
        )
        .order_by(MessageHistory.created_at.desc())
        .limit(limit)
    )
    entries = result.scalars().all()

    evaluated = 0
    failed = 0
    scores_accum: dict[str, list[int]] = {
        'relevance': [], 'politeness': [], 'completeness': [], 'accuracy': [],
    }

    for entry in entries:
        ev = await evaluate_history_entry(db, entry, strategy)
        if ev and ev.overall > 0:
            evaluated += 1
            for key in scores_accum:
                val = getattr(ev, key, 0)
                if val > 0:
                    scores_accum[key].append(val)
        else:
            failed += 1

    # Compute averages
    avg_scores: dict[str, float] = {}
    for key, vals in scores_accum.items():
        avg_scores[key] = sum(vals) / len(vals) if vals else 0.0

    return {
        'evaluated': evaluated,
        'failed': failed,
        'total': len(entries),
        'avg_scores': avg_scores,
        'overall_avg': sum(avg_scores.values()) / 4.0 if any(v > 0 for v in avg_scores.values()) else 0.0,
    }
