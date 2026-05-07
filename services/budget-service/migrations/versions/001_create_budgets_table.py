"""Create budgets table.

Revision ID: 001
Revises:
Create Date: 2026-04-30
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
        "budgets",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("budget_date", sa.Date, nullable=True),
        sa.Column("account_id", sa.Integer, nullable=False, index=True),
        sa.Column("category_id", sa.Integer, nullable=False, index=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=True),
    )


def downgrade() -> None:
    op.drop_table("budgets")
