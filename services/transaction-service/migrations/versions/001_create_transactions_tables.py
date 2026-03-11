"""Create transactions and planned_transactions tables.

Revision ID: 001
Revises:
Create Date: 2026-03-11
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, nullable=False, index=True),
        sa.Column("account_id", sa.Integer, nullable=False, index=True),
        sa.Column("account_name", sa.String(100), nullable=False),
        sa.Column("category_id", sa.Integer, nullable=True, index=True),
        sa.Column("category_name", sa.String(100), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("transaction_type", sa.String(20), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("date", sa.Date, nullable=False, index=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime, nullable=True),
    )

    op.create_table(
        "planned_transactions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, nullable=False, index=True),
        sa.Column("account_id", sa.Integer, nullable=False),
        sa.Column("account_name", sa.String(100), nullable=False),
        sa.Column("category_id", sa.Integer, nullable=True),
        sa.Column("category_name", sa.String(100), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("transaction_type", sa.String(20), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("recurrence", sa.String(20), nullable=False),
        sa.Column("next_execution", sa.Date, nullable=False, index=True),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("planned_transactions")
    op.drop_table("transactions")
