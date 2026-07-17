"""add in-flight sync-claim columns to bank_connections (P3-14)

Serializes bank-sync sagas per connection: start_sync_saga claims the
connection atomically (conditional UPDATE on these columns) so concurrent
sync requests share one saga instead of racing. Cleared on
mark_sync_complete; stale claims are stolen after status-check/TTL.

Revision ID: 003
Revises: 002
Create Date: 2026-07-17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("bank_connections", sa.Column("sync_saga_id", sa.String(36), nullable=True))
    op.add_column("bank_connections", sa.Column("sync_started_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("bank_connections", "sync_started_at")
    op.drop_column("bank_connections", "sync_saga_id")
