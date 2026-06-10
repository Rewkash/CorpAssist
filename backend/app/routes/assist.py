from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.generator import generator_service
from app.models import Conversation, MessageHistory, User
from app.nlp import nlp_service
from app.schemas import HistoryItem, ImproveDraftRequest, ImproveDraftResponse, SuggestReplyRequest, SuggestReplyResponse
from app.services.assist_context import build_client_context, build_conversation_context
from app.services.llm_guard import ensure_llm_ready

router = APIRouter()


@router.post('/assist/reply', response_model=SuggestReplyResponse)
async def suggest_reply(
    payload: SuggestReplyRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SuggestReplyResponse:
    ensure_llm_ready()
    analysis = await nlp_service.analyze(payload.text)
    context = ''
    if user.role == 'client':
        context = await build_client_context(db, user.id)
    elif user.role == 'worker' and payload.conversation_id:
        conv_result = await db.execute(select(Conversation).where(Conversation.id == payload.conversation_id))
        conv = conv_result.scalar_one_or_none()
        if conv and conv.client_id:
            context = await build_conversation_context(db, conv)
    suggestions = await generator_service.suggest_replies(payload.text, analysis, context)

    response = SuggestReplyResponse(analysis=analysis, suggestions=suggestions)

    db.add(
        MessageHistory(
            user_id=user.id,
            mode='reply',
            source_text=payload.text,
            result_text='\n---\n'.join(suggestions),
            sentiment=analysis.sentiment,
            topics=', '.join(analysis.topics),
            formality=analysis.formality,
        )
    )
    await db.commit()
    return response


@router.post('/assist/improve', response_model=ImproveDraftResponse)
async def improve_draft(
    payload: ImproveDraftRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ImproveDraftResponse:
    ensure_llm_ready()
    analysis = await nlp_service.analyze(payload.text)
    context = ''
    if user.role == 'client':
        context = await build_client_context(db, user.id)
    elif user.role == 'worker' and payload.conversation_id:
        conv_result = await db.execute(select(Conversation).where(Conversation.id == payload.conversation_id))
        conv = conv_result.scalar_one_or_none()
        if conv and conv.client_id:
            context = await build_conversation_context(db, conv)
    improved = await generator_service.improve_draft(payload.text, analysis, context)
    diff = nlp_service.make_diff(payload.text, improved)

    response = ImproveDraftResponse(analysis=analysis, improved_text=improved, diff=diff)

    db.add(
        MessageHistory(
            user_id=user.id,
            mode='improve',
            source_text=payload.text,
            result_text=improved,
            sentiment=analysis.sentiment,
            topics=', '.join(analysis.topics),
            formality=analysis.formality,
        )
    )
    await db.commit()
    return response


@router.get('/history', response_model=list[HistoryItem])
async def history(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[HistoryItem]:
    result = await db.execute(
        select(MessageHistory).where(MessageHistory.user_id == user.id).order_by(MessageHistory.created_at.desc()).limit(30)
    )
    return [HistoryItem.model_validate(row) for row in result.scalars().all()]
