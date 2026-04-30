"""Add processed_events (inbox) table for consumer deduplication.

Revision ID: 007
Revises: 006
Create Date: 2026-04-23

Same schema as categorization-service, standardised across the platform.
Used by TransactionCategorizedConsumer to deduplicate events.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "007"
down_revision: str = "006"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "processed_events",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("message_id", sa.String(36), nullable=False),
        sa.Column("consumer_name", sa.String(100), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "uq_processed_events",
        "processed_events",
        ["message_id", "consumer_name"],
        unique=True,
    )
    op.create_index("ix_processed_at", "processed_events", ["processed_at"])


def downgrade() -> None:
    op.drop_table("processed_events")
