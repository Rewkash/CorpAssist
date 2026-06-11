from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import require_role
from app.models import User
from app.schemas import AssignWorkerRequest, MeResponse

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
