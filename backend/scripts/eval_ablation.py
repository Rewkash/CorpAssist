#!/usr/bin/env python3
"""Ablation evaluation script: run all 6 strategies on same inputs.

Generates responses with each strategy and evaluates them via LLM-as-Judge.
Produces comparison tables suitable for thesis.

Usage:
    cd backend
    python -m scripts.eval_ablation --limit 20

Requires running backend with database + Ollama.
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models import (
    ChatMessage, ClientProfile, Conversation, ConversationSummary,
    EvaluationLog, MessageHistory, RAGSearchLog, User,
)
from app.generator import generator_service
from app.nlp import nlp_service
from app.services.assist_context import build_assist_context, _extract_current_topics, build_conversation_context
from app.services.client_memory import build_client_memory_context
from app.services.evaluation_service import evaluate_response
from app.services.rag_metrics import ALL_STRATEGIES

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

# Sample client messages for ablation (can be overridden with --input-file)
DEFAULT_MESSAGES = [
    "Добрый день! У нас возникла проблема с доступом к системе, не можем зайти в личный кабинет уже второй день.",
    "Здравствуйте, подскажите пожалуйста статус нашей заявки на интеграцию SAP от прошлого месяца?",
    "Приветствую! Хотим уточнить по поводу обновления тарифного плана, когда вступят в силу новые условия?",
    "Добрый день! У нас ошибка при выгрузке отчёта из 1С, помогите разобраться.",
    "Здравствуйте! Нам нужно настроить ЭДО с новым контрагентом, какие документы нужны?",
    "Добрый день, проблема с оплатой — счёт оплачен, но статус в системе не обновился.",
    "Приветствую! Когда будет готова доработка по кнопке экспорта, о которой мы говорили на прошлой неделе?",
    "Здравствуйте! У нас два сотрудника не могут подключиться к VPN, помогите пожалуйста.",
    "Добрый день, хотим уточнить по интеграции с нашей CRM системой, когда можно начать?",
    "Здравствуйте, у нас повторяется та же проблема с авторизацией, что и месяц назад.",
]


async def run_ablation(limit: int = 20, input_file: str | None = None) -> dict:
    """Run ablation: generate + evaluate same messages across all strategies."""
    generator_service.ensure_ready()

    # Load input messages
    messages = DEFAULT_MESSAGES[:limit]
    if input_file:
        with open(input_file, encoding='utf-8') as f:
            messages = json.load(f)[:limit]

    # Find a test worker + client pair
    async with AsyncSessionLocal() as db:
        worker_result = await db.execute(
            select(User).where(User.role == 'worker').limit(1)
        )
        worker = worker_result.scalar_one_or_none()
        if not worker:
            logger.error('No worker user found. Create a worker first.')
            return {}

        # Find client with most conversation summaries (richest memory)
        client_result = await db.execute(
            select(User).where(User.role == 'client').limit(1)
        )
        client = client_result.scalar_one_or_none()
        if not client:
            logger.error('No client user found. Create a client first.')
            return {}

        client_id = client.id
        logger.info('Using client_id=%d, worker_id=%d', client_id, worker.id)

        # Find a conversation for context extraction
        conv_result = await db.execute(
            select(Conversation)
            .where(Conversation.client_id == client_id)
            .order_by(Conversation.created_at.desc())
            .limit(1)
        )
        conversation = conv_result.scalar_one_or_none()

    results: dict[str, list[dict]] = {s: [] for s in ALL_STRATEGIES}
    rag_log_map: dict[str, int | None] = {}

    for msg_idx, client_message in enumerate(messages):
        logger.info('=== Message %d/%d: %s ===', msg_idx + 1, len(messages), client_message[:60])

        for strategy in ALL_STRATEGIES:
            async with AsyncSessionLocal() as db:
                # Build context with this strategy
                context = await build_client_memory_context(
                    db=db,
                    client_id=client_id,
                    current_topics=[],  # topics extracted from conversation if available
                    llm=generator_service._llm,
                    conversation_id=conversation.id if conversation else None,
                    strategy=strategy,
                )

                # Find and save the rag_search_log_id that was just created
                rag_log_id = None
                if strategy not in ('none', 'recent'):
                    rag_result = await db.execute(
                        select(RAGSearchLog)
                        .where(RAGSearchLog.client_id == client_id)
                        .order_by(RAGSearchLog.created_at.desc())
                        .limit(1)
                    )
                    rag_log = rag_result.scalar_one_or_none()
                    if rag_log:
                        rag_log_id = rag_log.id

                # Extract topics for NLP analysis
                analysis = await nlp_service.analyze(client_message)

                # Generate response
                try:
                    suggestions = await generator_service.suggest_replies(
                        client_message, analysis, context,
                    )
                    operator_response = suggestions[0] if suggestions else ''
                except Exception:
                    logger.exception('Generation failed for strategy=%s', strategy)
                    operator_response = ''

                if not operator_response:
                    results[strategy].append({
                        'message_idx': msg_idx,
                        'client_message': client_message[:200],
                        'strategy': strategy,
                        'error': 'generation_failed',
                    })
                    continue

                # Evaluate
                evaluation = await evaluate_response(
                    db=db,
                    client_message=client_message,
                    operator_response=operator_response,
                    strategy=strategy,
                    rag_search_log_id=rag_log_id,
                )

                entry = {
                    'message_idx': msg_idx,
                    'client_message': client_message[:200],
                    'strategy': strategy,
                    'context_length_chars': len(context),
                    'response_length_chars': len(operator_response),
                }
                if evaluation:
                    entry.update({
                        'relevance': evaluation.relevance,
                        'politeness': evaluation.politeness,
                        'completeness': evaluation.completeness,
                        'accuracy': evaluation.accuracy,
                        'overall': evaluation.overall,
                    })

                results[strategy].append(entry)
                logger.info(
                    '  strategy=%s: R=%d P=%d C=%d A=%d overall=%.1f ctx_len=%d',
                    strategy,
                    evaluation.relevance if evaluation else 0,
                    evaluation.politeness if evaluation else 0,
                    evaluation.completeness if evaluation else 0,
                    evaluation.accuracy if evaluation else 0,
                    evaluation.overall if evaluation else 0,
                    len(context),
                )

    # Compute summary statistics
    summary = _compute_summary(results)
    logger.info('\n===== ABLATION SUMMARY =====')
    for row in summary['table']:
        logger.info(
            '  %s: overall=%.2f  relevance=%.2f  completeness=%.2f  n=%d',
            row['strategy'],
            row.get('avg_overall', 0),
            row.get('avg_relevance', 0),
            row.get('avg_completeness', 0),
            row.get('n', 0),
        )
    logger.info('============================')

    # Save results
    output_path = Path(__file__).resolve().parent.parent / 'eval_ablation_results.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump({'detailed': results, 'summary': summary}, f, ensure_ascii=False, indent=2)
    logger.info('Results saved to %s', output_path)

    return summary


def _compute_summary(results: dict[str, list[dict]]) -> dict:
    """Compute per-strategy averages and ablation deltas."""
    table = []
    for strategy in ALL_STRATEGIES:
        entries = [e for e in results[strategy] if 'overall' in e and e.get('overall', 0) > 0]
        n = len(entries)
        if n == 0:
            table.append({'strategy': strategy, 'n': 0})
            continue

        avg = lambda key: sum(e[key] for e in entries) / n
        table.append({
            'strategy': strategy,
            'n': n,
            'avg_overall': round(avg('overall'), 2),
            'avg_relevance': round(avg('relevance'), 2),
            'avg_politeness': round(avg('politeness'), 2),
            'avg_completeness': round(avg('completeness'), 2),
            'avg_accuracy': round(avg('accuracy'), 2),
            'avg_context_length': round(sum(e['context_length_chars'] for e in entries) / n, 0),
            'avg_response_length': round(sum(e['response_length_chars'] for e in entries) / n, 0),
        })

    # Ablation deltas (vs 'none' baseline)
    none_row = next((r for r in table if r['strategy'] == 'none'), None)
    if none_row and none_row.get('n', 0) > 0:
        baseline = none_row.get('avg_overall', 0)
        for row in table:
            if row.get('n', 0) > 0:
                row['delta_vs_none'] = round(row.get('avg_overall', 0) - baseline, 2)

    return {'table': table}


def main():
    parser = argparse.ArgumentParser(description='Run RAG strategy ablation evaluation')
    parser.add_argument('--limit', type=int, default=20, help='Number of messages to evaluate')
    parser.add_argument('--input-file', type=str, default=None, help='JSON file with client messages')
    args = parser.parse_args()

    asyncio.run(run_ablation(limit=args.limit, input_file=args.input_file))


if __name__ == '__main__':
    main()
