"""add sync_trigger to bank_connections

Carries *what started this sync* alongside the P3-14 in-flight claim, so the
saga-reply handler can stamp `BankSyncCompletedEvent.trigger` and downstream
consumers can stay quiet about a nightly sweep that found nothing.

The claim row is the carrier because it already has exactly the right
lifetime: written when the saga starts, validated against saga_id when it
completes. That avoids threading the value through the saga envelope.

Nullable with no backfill -- rows claimed before this migration read as NULL
and the handler falls back to "manual".

Revision ID: 004
Revises: 003
Create Date: 2026-07-25
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("bank_connections", sa.Column("sync_trigger", sa.String(16), nullable=True))


def downgrade() -> None:
    op.drop_column("bank_connections", "sync_trigger")
