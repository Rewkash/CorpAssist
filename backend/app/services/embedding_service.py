"""Embedding generation and storage for conversation summaries.

Generates vector embeddings via Ollama's /api/embed endpoint and stores
them in the conversation_summaries.embedding column (pgvector).

This module is designed for graceful degradation: if Ollama or the
embedding model is unavailable, the system falls back to topic-match only.
"""

import logging

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.ollama_client import OllamaClient
from app.models import ConversationSummary, _HAS_PGVECTOR
from app.config import settings

logger = logging.getLogger(__name__)


def get_embedding_model() -> str:
    return settings.embedding_model


def is_pgvector_available() -> bool:
    """Check if pgvector extension is available (Python package + DB column)."""
    return _HAS_PGVECTOR


async def generate_embedding(llm: OllamaClient, text: str) -> list[float]:
    """Generate an embedding vector for the given text.

    Returns empty list if the embedding model is unavailable.
    """
    if not is_pgvector_available():
        return []
    return await llm.embed(text, model=get_embedding_model())


async def embed_conversation_summary(
    db: AsyncSession,
    llm: OllamaClient,
    summary: ConversationSummary,
) -> bool:
    """Generate and store embedding for a conversation summary.

    Returns True if embedding was successfully generated and saved.
    Returns False if pgvector is not available or embedding generation failed.
    The summary object is updated in-place and flushed to DB.
    """
    if not is_pgvector_available():
        logger.debug('pgvector not available, skipping embedding for summary %d', summary.id)
        return False

    # Build text for embedding: summary + key topics for richer semantic signal
    embed_text = summary.summary
    topics = summary.get_key_topics()
    if topics:
        embed_text = f'{summary.summary} Темы: {", ".join(topics)}'

    embedding = await generate_embedding(llm, embed_text)
    if not embedding:
        logger.warning('Failed to generate embedding for summary %d', summary.id)
        return False

    # Store embedding using raw SQL (pgvector type not directly compatible with ORM update)
    from sqlalchemy import text as sa_text
    await db.execute(
        sa_text(
            'UPDATE conversation_summaries SET embedding = :embedding WHERE id = :id'
        ),
        {'embedding': str(embedding), 'id': summary.id},
    )
    await db.flush()

    logger.info('Generated embedding for summary %d (dim=%d)', summary.id, len(embedding))
    return True


async def embed_query(llm: OllamaClient, query_text: str) -> list[float]:
    """Generate embedding for a search query (current conversation context).

    Returns empty list if embedding model is unavailable.
    """
    return await generate_embedding(llm, query_text)
