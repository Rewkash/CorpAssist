"""baseline current schema

Revision ID: 20260610_0001
Revises: 
Create Date: 2026-06-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260610_0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=20), server_default='client', nullable=False),
        sa.Column('assigned_worker_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['assigned_worker_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)
    op.create_index('ix_users_role', 'users', ['role'], unique=False)
    op.create_index('ix_users_assigned_worker_id', 'users', ['assigned_worker_id'], unique=False)

    op.create_table(
        'message_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('mode', sa.String(length=32), nullable=False),
        sa.Column('source_text', sa.Text(), nullable=False),
        sa.Column('result_text', sa.Text(), nullable=False),
        sa.Column('sentiment', sa.String(length=32), nullable=False),
        sa.Column('topics', sa.String(length=255), nullable=False),
        sa.Column('formality', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_message_history_user_id', 'message_history', ['user_id'], unique=False)
    op.create_index('ix_message_history_mode', 'message_history', ['mode'], unique=False)
    op.create_index('ix_message_history_created_at', 'message_history', ['created_at'], unique=False)

    op.create_table(
        'conversations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('client_id', sa.Integer(), nullable=False),
        sa.Column('worker_id', sa.Integer(), nullable=True),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=20), server_default='open', nullable=False),
        sa.Column('tags', sa.Text(), server_default='[]', nullable=False),
        sa.Column('tags_generated', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('priority_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['client_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['worker_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_conversations_client_id', 'conversations', ['client_id'], unique=False)
    op.create_index('ix_conversations_worker_id', 'conversations', ['worker_id'], unique=False)
    op.create_index('ix_conversations_status', 'conversations', ['status'], unique=False)
    op.create_index('ix_conversations_priority_at', 'conversations', ['priority_at'], unique=False)
    op.create_index('ix_conversations_created_at', 'conversations', ['created_at'], unique=False)

    op.create_table(
        'chat_messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('conversation_id', sa.Integer(), nullable=False),
        sa.Column('sender_id', sa.Integer(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=20), server_default='sent', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['sender_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_chat_messages_conversation_id', 'chat_messages', ['conversation_id'], unique=False)
    op.create_index('ix_chat_messages_sender_id', 'chat_messages', ['sender_id'], unique=False)
    op.create_index('ix_chat_messages_status', 'chat_messages', ['status'], unique=False)
    op.create_index('ix_chat_messages_created_at', 'chat_messages', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_chat_messages_created_at', table_name='chat_messages')
    op.drop_index('ix_chat_messages_status', table_name='chat_messages')
    op.drop_index('ix_chat_messages_sender_id', table_name='chat_messages')
    op.drop_index('ix_chat_messages_conversation_id', table_name='chat_messages')
    op.drop_table('chat_messages')

    op.drop_index('ix_conversations_created_at', table_name='conversations')
    op.drop_index('ix_conversations_priority_at', table_name='conversations')
    op.drop_index('ix_conversations_status', table_name='conversations')
    op.drop_index('ix_conversations_worker_id', table_name='conversations')
    op.drop_index('ix_conversations_client_id', table_name='conversations')
    op.drop_table('conversations')

    op.drop_index('ix_message_history_created_at', table_name='message_history')
    op.drop_index('ix_message_history_mode', table_name='message_history')
    op.drop_index('ix_message_history_user_id', table_name='message_history')
    op.drop_table('message_history')

    op.drop_index('ix_users_assigned_worker_id', table_name='users')
    op.drop_index('ix_users_role', table_name='users')
    op.drop_index('ix_users_email', table_name='users')
    op.drop_table('users')
