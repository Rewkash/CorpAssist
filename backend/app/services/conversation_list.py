from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Conversation, User
from app.schemas import ConversationItem
from app.services.conversation_presenter import build_conversation_items


async def list_conversations_for_user(
    db: AsyncSession,
    user: User,
) -> list[ConversationItem]:
    if user.role == 'client':
        result = await db.execute(
            select(Conversation)
            .where(Conversation.client_id == user.id)
            .order_by(Conversation.priority_at.asc().nullslast(), Conversation.created_at.desc())
        )
    elif user.role == 'worker':
        result = await db.execute(
            select(Conversation)
            .where((Conversation.worker_id == user.id) | ((Conversation.worker_id.is_(None)) & (Conversation.status == 'open')))
            .order_by(Conversation.priority_at.asc().nullslast(), Conversation.created_at.desc())
        )
    else:
        result = await db.execute(
            select(Conversation)
            .order_by(Conversation.priority_at.asc().nullslast(), Conversation.created_at.desc())
            .limit(100)
        )
    rows = result.scalars().all()
    return await build_conversation_items(db, user, rows)
