from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Conversation, User


async def get_accessible_conversation(db: AsyncSession, user: User, conversation_id: int) -> Conversation:
    conv_result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    conversation = conv_result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail='Диалог не найден')
    if user.role != 'admin' and user.id not in (conversation.client_id, conversation.worker_id):
        raise HTTPException(status_code=403, detail='Нет доступа к диалогу')
    return conversation
