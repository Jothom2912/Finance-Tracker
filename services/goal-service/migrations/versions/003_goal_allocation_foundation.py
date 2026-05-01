"""add goal allocation foundation

Revision ID: 003
Revises: 002
Create Date: 2026-05-01 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "goals",
        sa.Column(
            "is_default_savings_goal",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.create_index(
        "ix_goals_one_default_per_account",
        "goals",
        ["Account_idAccount"],
        unique=True,
        postgresql_where=sa.text("is_default_savings_goal = TRUE"),
        sqlite_where=sa.text("is_default_savings_goal = 1"),
    )

    op.create_table(
        "goal_allocation_history",
        sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True),
        sa.Column("source_key", sa.String(255), nullable=False),
        sa.Column("goal_id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("correlation_id", sa.Uuid(as_uuid=False), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["goal_id"], ["goals.idGoal"]),
        sa.CheckConstraint("amount > 0", name="ck_goal_allocation_history_positive_amount"),
        sa.UniqueConstraint("source_key", "goal_id", name="uq_goal_allocation_history_source_goal"),
    )
    op.create_index("ix_goal_allocation_history_goal_id", "goal_allocation_history", ["goal_id"])
    op.create_index("ix_goal_allocation_history_source_key", "goal_allocation_history", ["source_key"])

    op.create_table(
        "unallocated_budget_surplus",
        sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True),
        sa.Column("source_key", sa.String(255), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("reason", sa.String(50), nullable=False),
        sa.Column("correlation_id", sa.Uuid(as_uuid=False), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("amount > 0", name="ck_unallocated_budget_surplus_positive_amount"),
        sa.UniqueConstraint("source_key", name="uq_unallocated_budget_surplus_source_key"),
    )
    op.create_index("ix_unallocated_budget_surplus_account_id", "unallocated_budget_surplus", ["account_id"])


def downgrade() -> None:
    op.drop_index("ix_unallocated_budget_surplus_account_id", table_name="unallocated_budget_surplus")
    op.drop_table("unallocated_budget_surplus")

    op.drop_index("ix_goal_allocation_history_source_key", table_name="goal_allocation_history")
    op.drop_index("ix_goal_allocation_history_goal_id", table_name="goal_allocation_history")
    op.drop_table("goal_allocation_history")

    op.drop_index("ix_goals_one_default_per_account", table_name="goals")
    op.drop_column("goals", "is_default_savings_goal")
