from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import create_access_token, hash_password, verify_password
from app.database import get_db
from app.deps import get_current_user
from app.main import limiter
from app.models import User
from app.schemas import LoginRequest, MeResponse, RegisterRequest, TokenResponse

router = APIRouter()


@router.post('/auth/register', response_model=TokenResponse)
@limiter.limit('5/minute')
async def register(request: Request, payload: RegisterRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail='User already exists')

    user = User(email=payload.email, password_hash=hash_password(payload.password), role=payload.role)
    db.add(user)
    await db.commit()
    return TokenResponse(access_token=create_access_token(payload.email))


@router.post('/auth/login', response_model=TokenResponse)
@limiter.limit('5/minute')
async def login(request: Request, payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail='Invalid credentials')
    return TokenResponse(access_token=create_access_token(payload.email))


@router.get('/auth/me', response_model=MeResponse)
async def me(user: User = Depends(get_current_user)) -> MeResponse:
    return MeResponse(id=user.id, email=user.email, role=user.role, assigned_worker_id=user.assigned_worker_id)
