"""add deleted_at to goals (soft-delete)

Goals with goal_allocation_history rows cannot be hard-deleted (plain FK,
no ON DELETE) — see finding F-2026-07-17-01 / backlog P3-16. Soft-delete
preserves the allocation audit trail; the delete-path clears
is_default_savings_goal in the same statement, so the partial unique index
ix_goals_one_default_per_account needs no change.

Revision ID: 005
Revises: 004
Create Date: 2026-07-17 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: str = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # batch_alter_table: plain ALTER på Postgres, table-recreate på sqlite
    # (migrations-testsuiten kører mod sqlite — finding F-2026-07-12-01).
    with op.batch_alter_table("goals") as batch:
        batch.add_column(sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    # Soft-deleted rækker mister deres slettemarkering og genopstår som
    # aktive mål — acceptabelt i et rollback-vindue (data er ikke korrupt).
    with op.batch_alter_table("goals") as batch:
        batch.drop_column("deleted_at")
