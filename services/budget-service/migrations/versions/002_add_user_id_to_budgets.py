"""Add user_id to budgets table.

Revision ID: 002
Revises: 001
Create Date: 2026-05-07
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "budgets",
        sa.Column("user_id", sa.Integer, nullable=False, server_default="0"),
    )
    op.create_index("ix_budgets_user_id", "budgets", ["user_id"])
    # Remove the server_default after backfill — existing rows get 0 as a sentinel
    op.alter_column("budgets", "user_id", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_budgets_user_id", table_name="budgets")
    op.drop_column("budgets", "user_id")
