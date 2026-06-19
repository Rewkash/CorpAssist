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

    # One aggregating query instead of 3 per conversation
    conversation_ids = [row.id for row in rows]
    unread_map: dict[int, int] = {}
    msg_count_map: dict[int, int] = {}
    preview_map: dict[int, str | None] = {}

    if conversation_ids:
        agg_result = await db.execute(
            text(
                """
                SELECT
                    sub.conversation_id,
                    sub.total,
                    sub.unread,
                    p.first_text
                FROM (
                    SELECT
                        m.conversation_id,
                        COUNT(*) AS total,
                        SUM(CASE WHEN m.sender_id != :viewer_id AND m.status IN ('sent', 'delivered') THEN 1 ELSE 0 END) AS unread
                    FROM chat_messages m
                    WHERE m.conversation_id = ANY(:conversation_ids)
                    GROUP BY m.conversation_id
                ) sub
                LEFT JOIN LATERAL (
                    SELECT m2.text AS first_text
                    FROM chat_messages m2
                    WHERE m2.conversation_id = sub.conversation_id
                    ORDER BY m2.created_at ASC
                    LIMIT 1
                ) p ON TRUE
                """
            ),
            {'viewer_id': user.id, 'conversation_ids': conversation_ids},
        )
        for row in agg_result.fetchall():
            unread_map[row[0]] = int(row[2] or 0)
            msg_count_map[row[0]] = int(row[1] or 0)
            preview_map[row[0]] = row[3]

    items: list[ConversationItem] = []
    for row in rows:
        parsed_tags = row.get_tags()
        items.append(
            ConversationItem(
                id=row.id,
                title=row.title,
                client_id=row.client_id,
                client_email=client_emails.get(row.client_id),
                worker_id=row.worker_id,
                status=row.status,
                unread_count=unread_map.get(row.id, 0),
                tags=parsed_tags,
                priority_at=row.priority_at,
                message_count=msg_count_map.get(row.id, 0),
                first_message_preview=preview_map.get(row.id),
                created_at=row.created_at,
                closed_at=row.closed_at,
            )
        )
    return items
