"""add conversation_summaries and client_profiles

Revision ID: 20260619_0001
Revises: 20260610_0002
Create Date: 2026-06-19 00:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260619_0001'
down_revision: Union[str, None] = '20260610_0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'conversation_summaries',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('conversation_id', sa.Integer(), sa.ForeignKey('conversations.id', ondelete='CASCADE'), unique=True, nullable=False),
        sa.Column('client_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('key_topics', sa.Text(), server_default='[]'),
        sa.Column('resolution', sa.String(50), server_default=''),
        sa.Column('sentiment_trend', sa.String(50), server_default=''),
        sa.Column('generated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_conversation_summaries_conversation_id', 'conversation_summaries', ['conversation_id'], unique=True)
    op.create_index('ix_conversation_summaries_client_id', 'conversation_summaries', ['client_id'])

    op.create_table(
        'client_profiles',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('client_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), unique=True, nullable=False),
        sa.Column('profile', sa.Text(), server_default=''),
        sa.Column('common_topics', sa.Text(), server_default='[]'),
        sa.Column('communication_style', sa.String(50), server_default=''),
        sa.Column('interaction_count', sa.Integer(), server_default='0'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_client_profiles_client_id', 'client_profiles', ['client_id'], unique=True)


def downgrade() -> None:
    op.drop_table('client_profiles')
    op.drop_table('conversation_summaries')
