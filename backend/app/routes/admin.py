from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal, get_db
from app.deps import require_role
from app.models import Conversation, ConversationSummary, User
from app.schemas import AssignWorkerRequest, MeResponse
from app.services.conversation_summarizer import summarize_conversation
from app.services.embedding_service import embed_conversation_summary, is_pgvector_available

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
    client_result = await db.execute(select(User).where(User.id == payload.client_id, User.role == 'client'))
    worker_result = await db.execute(select(User).where(User.id == payload.worker_id, User.role == 'worker'))
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
    """Generate summaries for all closed conversations that don't have one yet.

    This is a one-time bootstrap endpoint for retroactively populating
    client long-term memory from existing conversation history.
    Runs summarization sequentially to avoid overwhelming the LLM.
    """
    # Find closed conversations without summaries
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
    """Generate embeddings for all conversation summaries that don't have one yet.

    This is a one-time bootstrap for retroactively populating vector
    embeddings from existing summaries. Requires pgvector extension.
    """
    if not is_pgvector_available():
        return {'error': 'pgvector not available', 'generated': 0, 'total': 0}

    from app.generator import generator_service

    # Find summaries without embeddings (use raw SQL for pgvector compatibility)
    result = await db.execute(
        sa_text('SELECT * FROM conversation_summaries WHERE embedding IS NULL ORDER BY generated_at ASC')
    )
    rows = result.fetchall()
    summary_ids = [row.id for row in rows]

    generated = 0
    failed = 0
    for sm_id in summary_ids:
        try:
            async with AsyncSessionLocal() as bg_db:
                sm_result = await bg.execute(
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
