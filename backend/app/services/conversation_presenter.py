import json

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Conversation, User
from app.schemas import ConversationItem


async def build_conversation_items(db: AsyncSession, user: User, rows: list[Conversation]) -> list[ConversationItem]:
    client_ids = {row.client_id for row in rows}
    client_emails: dict[int, str] = {}
    if client_ids:
        client_result = await db.execute(select(User.id, User.email).where(User.id.in_(client_ids)))
        client_emails = {row.id: row.email for row in client_result.all()}
    items: list[ConversationItem] = []
    for row in rows:
        unread_result = await db.execute(
            text(
                """
                SELECT COUNT(*)
                FROM chat_messages
                WHERE conversation_id = :conversation_id
                  AND sender_id != :viewer_id
                  AND status IN ('sent', 'delivered')
                """
            ),
            {'conversation_id': row.id, 'viewer_id': user.id},
        )
        unread_count = int(unread_result.scalar_one() or 0)
        msg_count_result = await db.execute(
            text('SELECT COUNT(*) FROM chat_messages WHERE conversation_id = :conversation_id'),
            {'conversation_id': row.id},
        )
        message_count = int(msg_count_result.scalar_one() or 0)
        preview_result = await db.execute(
            text(
                """
                SELECT text
                FROM chat_messages
                WHERE conversation_id = :conversation_id
                ORDER BY created_at ASC
                LIMIT 1
                """
            ),
            {'conversation_id': row.id},
        )
        first_message_preview = preview_result.scalar_one_or_none()
        parsed_tags: list[str] = []
        if row.tags:
            try:
                loaded = json.loads(row.tags)
                if isinstance(loaded, list):
                    parsed_tags = [str(tag).strip() for tag in loaded if str(tag).strip()]
            except Exception:
                parsed_tags = []
        items.append(
            ConversationItem(
                id=row.id,
                title=row.title,
                client_id=row.client_id,
                client_email=client_emails.get(row.client_id),
                worker_id=row.worker_id,
                status=row.status,
                unread_count=unread_count,
                tags=parsed_tags,
                priority_at=row.priority_at,
                message_count=message_count,
                first_message_preview=first_message_preview,
                created_at=row.created_at,
                closed_at=row.closed_at,
            )
        )
    return items
