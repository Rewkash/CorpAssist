from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ChatMessage, Conversation


async def build_client_context(db: AsyncSession, client_id: int) -> str:
    result = await db.execute(
        select(ChatMessage)
        .join(Conversation, Conversation.id == ChatMessage.conversation_id)
        .where(Conversation.client_id == client_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(20)
    )
    items = result.scalars().all()
    result_lines: list[str] = []
    for item in reversed(items):
        role = 'Клиент' if item.sender_id == client_id else 'Оператор'
        result_lines.append(f'{role}: {item.text}')
    return '\n'.join(result_lines)


async def build_conversation_context(db: AsyncSession, conversation: Conversation) -> str:
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.conversation_id == conversation.id)
        .order_by(ChatMessage.created_at.desc())
        .limit(30)
    )
    items = result.scalars().all()
    result_lines: list[str] = []
    for item in reversed(items):
        role = 'Клиент' if item.sender_id == conversation.client_id else 'Оператор'
        result_lines.append(f'{role}: {item.text}')
    return '\n'.join(result_lines)
