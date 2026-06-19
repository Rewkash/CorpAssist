from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Conversation, User
from app.realtime.hubs import UserSocketHub
from app.services.conversation_list import list_conversations_for_user


async def push_conversations_snapshot(
    db: AsyncSession,
    conversation: Conversation,
    *,
    user_socket_hub: UserSocketHub,
) -> None:
    target_user_ids = {conversation.client_id}
    if conversation.worker_id:
        target_user_ids.add(conversation.worker_id)

    admin_result = await db.execute(select(User.id).where(User.role == 'admin'))
    target_user_ids.update(row.id for row in admin_result.all())

    if not target_user_ids:
        return

    # Fetch all target users in one query instead of N individual lookups
    viewers_result = await db.execute(select(User).where(User.id.in_(target_user_ids)))
    viewers = {viewer.id: viewer for viewer in viewers_result.scalars().all()}

    for user_id in target_user_ids:
        viewer = viewers.get(user_id)
        if not viewer:
            continue
        items = await list_conversations_for_user(db, viewer)
        await user_socket_hub.send_to_user(
            user_id,
            {
                'type': 'conversations_snapshot',
                'payload': [item.model_dump(mode='json') for item in items],
            },
        )
