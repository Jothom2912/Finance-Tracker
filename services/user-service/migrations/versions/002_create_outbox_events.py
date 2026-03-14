"""Create outbox_events table for transactional outbox pattern.

Revision ID: 002
Revises: 001
Create Date: 2026-03-14
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: str = "001"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "outbox_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("aggregate_type", sa.String(length=50), nullable=False),
        sa.Column("aggregate_id", sa.String(length=100), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("correlation_id", sa.String(length=36), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "attempts", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "next_attempt_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_outbox_pending_poll",
        "outbox_events",
        ["status", "next_attempt_at", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_outbox_pending_poll", table_name="outbox_events")
    op.drop_table("outbox_events")
