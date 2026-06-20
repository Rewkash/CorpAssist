"""add RAGSearchLog and EvaluationLog tables

Revision ID: 20260621_0001
Revises: 20260620_0001
Create Date: 2026-06-21 00:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '20260621_0001'
down_revision: Union[str, None] = '20260620_0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'rag_search_logs',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('client_id', sa.Integer(), nullable=False),
        sa.Column('conversation_id', sa.Integer(), nullable=True),
        sa.Column('current_topics', sa.Text(), server_default='[]'),
        sa.Column('strategy', sa.String(32), nullable=False),
        sa.Column('results_count', sa.Integer(), server_default='0'),
        sa.Column('topic_hits', sa.Integer(), server_default='0'),
        sa.Column('vector_hits', sa.Integer(), server_default='0'),
        sa.Column('rrf_scores', sa.Text(), server_default='[]'),
        sa.Column('hit_summary_ids', sa.Text(), server_default='[]'),
        sa.Column('latency_ms', sa.Integer(), server_default='0'),
    )
    op.create_index('ix_rag_search_logs_created_at', 'rag_search_logs', ['created_at'])
    op.create_index('ix_rag_search_logs_client_id', 'rag_search_logs', ['client_id'])
    op.create_index('ix_rag_search_logs_strategy', 'rag_search_logs', ['strategy'])

    op.create_table(
        'llm_evaluations',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('message_history_id', sa.Integer(), nullable=True),
        sa.Column('strategy', sa.String(32), nullable=False),
        sa.Column('relevance', sa.Integer(), server_default='0'),
        sa.Column('politeness', sa.Integer(), server_default='0'),
        sa.Column('completeness', sa.Integer(), server_default='0'),
        sa.Column('accuracy', sa.Integer(), server_default='0'),
        sa.Column('overall', sa.Float(), server_default='0.0'),
        sa.Column('judge_model', sa.String(64), server_default=''),
        sa.Column('judge_raw', sa.Text(), server_default=''),
    )
    op.create_index('ix_llm_evaluations_created_at', 'llm_evaluations', ['created_at'])
    op.create_index('ix_llm_evaluations_strategy', 'llm_evaluations', ['strategy'])
    op.create_index('ix_llm_evaluations_message_history_id', 'llm_evaluations', ['message_history_id'])


def downgrade() -> None:
    op.drop_table('llm_evaluations')
    op.drop_table('rag_search_logs')
