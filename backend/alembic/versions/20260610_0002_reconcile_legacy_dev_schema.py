"""reconcile legacy dev schema

Revision ID: 20260610_0002
Revises: 20260610_0001
Create Date: 2026-06-10 00:05:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '20260610_0002'
down_revision: Union[str, None] = '20260610_0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Legacy extra ix_*_id indexes are intentionally left in place.
    # They do not break application behavior, and removing them is a separate
    # performance/schema cleanup decision.

    op.execute("UPDATE users SET assigned_worker_id = NULL WHERE assigned_worker_id IS NOT NULL AND assigned_worker_id NOT IN (SELECT id FROM users)")
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'users_assigned_worker_id_fkey'
                  AND conrelid = 'users'::regclass
            ) THEN
                ALTER TABLE users
                    ADD CONSTRAINT users_assigned_worker_id_fkey
                    FOREIGN KEY (assigned_worker_id)
                    REFERENCES users(id)
                    ON DELETE SET NULL;
            END IF;
        END
        $$;
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'conversations_worker_id_fkey'
                  AND conrelid = 'conversations'::regclass
            ) THEN
                ALTER TABLE conversations DROP CONSTRAINT conversations_worker_id_fkey;
            END IF;

            ALTER TABLE conversations
                ADD CONSTRAINT conversations_worker_id_fkey
                FOREIGN KEY (worker_id)
                REFERENCES users(id)
                ON DELETE SET NULL;
        END
        $$;
        """
    )

    op.execute("UPDATE users SET role = 'client' WHERE role IS NULL")
    op.execute("ALTER TABLE users ALTER COLUMN role SET DEFAULT 'client'")
    op.execute("ALTER TABLE users ALTER COLUMN role SET NOT NULL")

    op.execute("UPDATE conversations SET status = 'open' WHERE status IS NULL")
    op.execute("ALTER TABLE conversations ALTER COLUMN status SET DEFAULT 'open'")
    op.execute("ALTER TABLE conversations ALTER COLUMN status SET NOT NULL")

    op.execute("UPDATE conversations SET tags = '[]' WHERE tags IS NULL")
    op.execute("ALTER TABLE conversations ALTER COLUMN tags SET DEFAULT '[]'")
    op.execute("ALTER TABLE conversations ALTER COLUMN tags SET NOT NULL")

    op.execute("UPDATE conversations SET tags_generated = false WHERE tags_generated IS NULL")
    op.execute("ALTER TABLE conversations ALTER COLUMN tags_generated SET DEFAULT false")
    op.execute("ALTER TABLE conversations ALTER COLUMN tags_generated SET NOT NULL")

    op.execute("UPDATE chat_messages SET status = 'sent' WHERE status IS NULL")
    op.execute("ALTER TABLE chat_messages ALTER COLUMN status SET DEFAULT 'sent'")
    op.execute("ALTER TABLE chat_messages ALTER COLUMN status SET NOT NULL")


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'users_assigned_worker_id_fkey'
                  AND conrelid = 'users'::regclass
            ) THEN
                ALTER TABLE users DROP CONSTRAINT users_assigned_worker_id_fkey;
            END IF;
        END
        $$;
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'conversations_worker_id_fkey'
                  AND conrelid = 'conversations'::regclass
            ) THEN
                ALTER TABLE conversations DROP CONSTRAINT conversations_worker_id_fkey;
            END IF;

            ALTER TABLE conversations
                ADD CONSTRAINT conversations_worker_id_fkey
                FOREIGN KEY (worker_id)
                REFERENCES users(id)
                ON DELETE CASCADE;
        END
        $$;
        """
    )

    op.execute("ALTER TABLE chat_messages ALTER COLUMN status DROP NOT NULL")
    op.execute("ALTER TABLE conversations ALTER COLUMN tags_generated DROP NOT NULL")
    op.execute("ALTER TABLE conversations ALTER COLUMN tags DROP NOT NULL")
    op.execute("ALTER TABLE conversations ALTER COLUMN status DROP NOT NULL")
    op.execute("ALTER TABLE users ALTER COLUMN role DROP NOT NULL")
