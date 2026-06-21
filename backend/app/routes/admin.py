from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal, get_db
from app.deps import require_role
from app.models import Conversation, ConversationSummary, EvaluationLog, User
from app.schemas import AssignWorkerRequest, MeResponse
from app.services.conversation_summarizer import summarize_conversation
from app.services.embedding_service import embed_conversation_summary, is_pgvector_available
from app.services.evaluation_service import evaluate_response, batch_evaluate
from app.services.rag_metrics import (
    get_rag_summary, get_rag_comparison, get_eval_summary,
    get_eval_comparison, get_full_comparison, ALL_STRATEGIES,
)

router = APIRouter()


@router.get('/admin/workers', response_model=list[MeResponse])
async def list_workers(
    _: User = Depends(require_role('admin')),
    db: AsyncSession = Depends(get_db),
) -> list[MeResponse]:
    result = await db.execute(select(User).where(User.role == 'worker').order_by(User.created_at.desc()))
    workers = result.scalars().all()
    return [MeResponse(id=w.id, email=w.email, role=w.role, assigned_worker_id=w.assigned_worker_id) for w in workers]


@router.get('/admin/clients', response_model=list[MeResponse])
async def list_clients(
    _: User = Depends(require_role('admin')),
    db: AsyncSession = Depends(get_db),
) -> list[MeResponse]:
    result = await db.execute(select(User).where(User.role == 'client').order_by(User.created_at.desc()))
    clients = result.scalars().all()
    return [MeResponse(id=c.id, email=c.email, role=c.role, assigned_worker_id=c.assigned_worker_id) for c in clients]


@router.post('/admin/assign-worker')
async def assign_worker(
    payload: AssignWorkerRequest,
    _: User = Depends(require_role('admin')),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    client_result = await db.execute(select(User).where(User.id == payload.client_id))
    worker_result = await db.execute(select(User).where(User.id == payload.worker_id))
    client = client_result.scalar_one_or_none()
    worker = worker_result.scalar_one_or_none()
    if not client or not worker:
        raise HTTPException(status_code=404, detail='Клиент или сотрудник не найден')
    client.assigned_worker_id = worker.id
    await db.commit()
    return {'status': 'ok'}


@router.post('/admin/bootstrap-memory')
async def bootstrap_memory(
    _: User = Depends(require_role('admin')),
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    """Generate summaries for all closed conversations that don't have one yet."""
    existing_ids = select(ConversationSummary.conversation_id)
    result = await db.execute(
        select(Conversation)
        .where(Conversation.status == 'closed', ~Conversation.id.in_(existing_ids))
        .order_by(Conversation.created_at.asc())
    )
    conversations = result.scalars().all()

    generated = 0
    failed = 0
    for conv in conversations:
        try:
            async with AsyncSessionLocal() as bg_db:
                summary = await summarize_conversation(bg_db, conv)
                if summary:
                    generated += 1
        except Exception:
            failed += 1

    return {'generated': generated, 'failed': failed, 'total_closed': len(conversations)}


@router.post('/admin/bootstrap-embeddings')
async def bootstrap_embeddings(
    _: User = Depends(require_role('admin')),
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    """Generate embeddings for all conversation summaries that don't have one yet."""
    if not is_pgvector_available():
        return {'error': 'pgvector not available', 'generated': 0, 'total': 0}

    from app.generator import generator_service

    result = await db.execute(
        sa_text('SELECT id FROM conversation_summaries WHERE embedding IS NULL ORDER BY generated_at ASC')
    )
    summary_ids = [row.id for row in result.fetchall()]

    generated = 0
    failed = 0
    for sm_id in summary_ids:
        try:
            async with AsyncSessionLocal() as bg_db:
                sm_result = await bg_db.execute(
                    select(ConversationSummary).where(ConversationSummary.id == sm_id)
                )
                sm = sm_result.scalar_one_or_none()
                if not sm:
                    continue
                ok = await embed_conversation_summary(bg_db, generator_service._llm, sm)
                if ok:
                    await bg_db.commit()
                    generated += 1
                else:
                    failed += 1
        except Exception:
            failed += 1

    return {'generated': generated, 'failed': failed, 'total': len(summary_ids)}


# ──────────────────────── Evaluation Endpoints ────────────────────────


@router.post('/eval/run')
async def run_evaluation(
    _: User = Depends(require_role('admin')),
    db: AsyncSession = Depends(get_db),
    strategy: str | None = None,
    limit: int = 50,
) -> dict:
    """Run LLM-as-Judge evaluation on un-evaluated reply suggestions.

    Query params:
      - strategy: filter by memory strategy (default: all)
      - limit: max entries to evaluate (default: 50)
    """
    result = await batch_evaluate(db, strategy=strategy, limit=limit)
    return result


@router.get('/eval/rag-summary')
async def rag_search_summary(
    _: User = Depends(require_role('admin')),
    db: AsyncSession = Depends(get_db),
    strategy: str | None = None,
) -> dict:
    """RAG search metrics summary, optionally filtered by strategy."""
    return await get_rag_summary(db, strategy=strategy)


@router.get('/eval/rag-comparison')
async def rag_search_comparison(
    _: User = Depends(require_role('admin')),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """RAG search metrics comparison across all strategies."""
    return await get_rag_comparison(db)


@router.get('/eval/scores-summary')
async def evaluation_scores_summary(
    _: User = Depends(require_role('admin')),
    db: AsyncSession = Depends(get_db),
    strategy: str | None = None,
) -> dict:
    """LLM-as-Judge evaluation scores summary."""
    return await get_eval_summary(db, strategy=strategy)


@router.get('/eval/scores-comparison')
async def evaluation_scores_comparison(
    _: User = Depends(require_role('admin')),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """LLM-as-Judge evaluation scores comparison across all strategies."""
    return await get_eval_comparison(db)


@router.get('/eval/full-comparison')
async def full_evaluation_comparison(
    _: User = Depends(require_role('admin')),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Combined RAG + evaluation comparison across all strategies.

    This is the primary endpoint for thesis data:
    one row per strategy with both search metrics and quality scores.
    Returns data suitable for building comparison tables and charts.
    """
    return await get_full_comparison(db)
