"""add strategy to message_history, rag_search_log_id to evaluations, context_length

Revision ID: 20260621_0002
Revises: 20260621_0001
Create Date: 2026-06-21 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '20260621_0002'
down_revision: Union[str, None] = '20260621_0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Fix 1: strategy in message_history
    op.add_column('message_history', sa.Column('strategy', sa.String(32), server_default='hybrid'))
    op.create_index('ix_message_history_strategy', 'message_history', ['strategy'])

    # Fix 1b: context_length_chars in message_history (confounder control)
    op.add_column('message_history', sa.Column('context_length_chars', sa.Integer(), server_default='0'))

    # Fix 2: rag_search_log_id in llm_evaluations
    op.add_column('llm_evaluations', sa.Column('rag_search_log_id', sa.Integer(), nullable=True))
    op.create_index(
        'ix_llm_evaluations_rag_search_log_id',
        'llm_evaluations',
        ['rag_search_log_id'],
    )
    op.create_foreign_key(
        'fk_llm_evaluations_rag_search_log_id',
        'llm_evaluations',
        'rag_search_logs',
        ['rag_search_log_id'],
        ['id'],
    )


def downgrade() -> None:
    op.drop_constraint('fk_llm_evaluations_rag_search_log_id', 'llm_evaluations', type_='foreignkey')
    op.drop_index('ix_llm_evaluations_rag_search_log_id', 'llm_evaluations')
    op.drop_column('llm_evaluations', 'rag_search_log_id')

    op.drop_column('message_history', 'context_length_chars')
    op.drop_index('ix_message_history_strategy', 'message_history')
    op.drop_column('message_history', 'strategy')
