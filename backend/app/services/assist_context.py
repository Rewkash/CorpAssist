from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ChatMessage, Conversation, User
from app.services.client_memory import build_client_memory_context


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


def _extract_current_topics(conversation: Conversation, last_client_message: str = '') -> list[str]:
    """Extract topics from conversation tags (primary), title, or last client message.

    Tags and title are preferred because they're already LLM-classified.
    As a fallback, simple keyword extraction from the last client message
    provides basic topic hints without calling the NLP pipeline.
    """
    topics: list[str] = []

    # Tags are the most reliable topic indicator
    tags = conversation.get_tags()
    topics.extend(tags)

    # Title (if not default) may contain useful info
    if conversation.title and conversation.title != 'Новый диалог':
        topics.append(conversation.title)

    # Fallback: extract significant words from last client message
    if not topics and last_client_message:
        _stop_words = {
            'ие', 'ый', 'ой', 'ая', 'яя', 'ое', 'ее', 'ию', 'ем', 'ет', 'ен',
            'от', 'на', 'в', 'и', 'с', 'по', 'к', 'у', 'за', 'из', 'от',
            'не', 'но', 'а', 'что', 'как', 'это', 'для', 'при', 'есть',
            'был', 'быть', 'может', 'будет', 'очень', 'тоже', 'ещё', 'уже',
            'нам', 'вас', 'вам', 'вы', 'мы', 'он', 'она', 'они', 'это',
            'я', 'мне', 'мой', 'моя', 'мое', 'свой', 'своя', 'свое',
            'все', 'всё', 'так', 'тут', 'где', 'там', 'кто', 'чем',
            'его', 'её', 'их', 'ей', 'ему', 'ним', 'ней', 'ними',
            'под', 'над', 'без', 'до', 'после', 'между', 'перед',
            'если', 'чтобы', 'потому', 'поэтому', 'пока', 'когда',
            'здравствуйте', 'привет', 'спасибо', 'пожалуйста',
        }
        words = last_client_message.lower().split()
        significant = [w for w in words if len(w) > 3 and w not in _stop_words]
        # Take top 3 unique significant words as topic hints
        seen: set[str] = set()
        for w in significant:
            if w not in seen:
                seen.add(w)
                topics.append(w.capitalize())
            if len(topics) >= 5:
                break

    return topics


async def build_assist_context(db: AsyncSession, user: User, conversation_id: int | None) -> str:
    """Build LLM context for assist endpoints with access check and long-term client memory.

    For workers: combines current conversation + client long-term memory (profile + summaries).
    The long-term memory uses hybrid search: topic-match + vector search with RRF fusion,
    so that past conversations about the same topic resurface even semantically.
    For clients: returns cross-conversation raw history (unchanged behavior).
    """
    if user.role == 'client':
        return await build_client_context(db, user.id)
    if user.role == 'worker' and conversation_id:
        from app.services.conversation_access import get_accessible_conversation
        from app.generator import generator_service
        try:
            conversation = await get_accessible_conversation(db, user, conversation_id)
        except Exception:
            return ''
        # Current conversation messages
        current_context = await build_conversation_context(db, conversation)
        # Extract topics from current dialog for relevance matching
        # Try conversation tags first; fall back to last client message
        last_client_msg = ''
        if current_context:
            # Find last line starting with "Клиент:"
            for line in reversed(current_context.splitlines()):
                if line.startswith('Клиент:'):
                    last_client_msg = line[len('Клиент:'):].strip()
                    break
        current_topics = _extract_current_topics(conversation, last_client_msg)
        # Long-term memory: client profile + recent + hybrid search summaries
        memory_context = await build_client_memory_context(
            db, conversation.client_id, current_topics,
            llm=generator_service._llm,
        )
        # Combine: memory first, then current conversation
        parts: list[str] = []
        if memory_context:
            parts.append(memory_context)
        if current_context:
            parts.append(f'📝 Текущий диалог:\n{current_context}')
        return '\n\n'.join(parts)
    return ''
