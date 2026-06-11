"""Add monthly_budgets, budget_lines, and outbox_events tables.

Revision ID: 003
Revises: 002
Create Date: 2026-06-11
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "monthly_budgets",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("month", sa.Integer, nullable=False),
        sa.Column("year", sa.Integer, nullable=False),
        sa.Column("account_id", sa.Integer, nullable=False),
        sa.Column("user_id", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint("account_id", "month", "year", name="uq_monthly_budget_account_period"),
    )
    op.create_index("ix_monthly_budgets_account_id", "monthly_budgets", ["account_id"])
    op.create_index("ix_monthly_budgets_user_id", "monthly_budgets", ["user_id"])

    op.create_table(
        "budget_lines",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "monthly_budget_id",
            sa.Integer,
            sa.ForeignKey("monthly_budgets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("category_id", sa.Integer, nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.UniqueConstraint("monthly_budget_id", "category_id", name="uq_budget_line_budget_category"),
    )

    op.create_table(
        "outbox_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("aggregate_type", sa.String(50), nullable=False),
        sa.Column("aggregate_id", sa.String(100), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("payload_json", sa.Text, nullable=False),
        sa.Column("correlation_id", sa.String(36), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("published_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_outbox_pending_poll", "outbox_events", ["status", "next_attempt_at", "created_at"])


def downgrade() -> None:
    op.drop_table("outbox_events")
    op.drop_table("budget_lines")
    op.drop_table("monthly_budgets")
