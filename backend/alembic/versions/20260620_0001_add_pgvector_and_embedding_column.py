"""add pgvector extension and embedding column to conversation_summaries

Revision ID: 20260620_0001
Revises: 20260619_0001
Create Date: 2026-06-20 00:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260620_0001'
down_revision: Union[str, None] = '20260619_0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBEDDING_DIMENSIONS = 768


def upgrade() -> None:
    # Enable pgvector extension
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')

    # Add embedding column to conversation_summaries
    op.execute(
        f'ALTER TABLE conversation_summaries '
        f'ADD COLUMN IF NOT EXISTS embedding vector({EMBEDDING_DIMENSIONS})'
    )

    # Create HNSW index for fast cosine similarity search
    # Only created when there's data; empty table is fine
    op.execute(
        'CREATE INDEX IF NOT EXISTS ix_conversation_summaries_embedding '
        'ON conversation_summaries '
        'USING hnsw (embedding vector_cosine_ops)'
    )


def downgrade() -> None:
    op.execute('DROP INDEX IF EXISTS ix_conversation_summaries_embedding')
    op.execute('ALTER TABLE conversation_summaries DROP COLUMN IF EXISTS embedding')
    op.execute('DROP EXTENSION IF EXISTS vector')
