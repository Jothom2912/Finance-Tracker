"""widen correlation_id from UUID to VARCHAR(255)

Deterministic source_key values (e.g. budget.month_closed:10:2026:6)
are stored in correlation_id for dedup — these are not valid UUIDs.

Revision ID: 004
Revises: 003
Create Date: 2026-06-11 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: str = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "goal_allocation_history",
        "correlation_id",
        existing_type=sa.Uuid(as_uuid=False),
        type_=sa.String(255),
        existing_nullable=True,
    )
    op.alter_column(
        "unallocated_budget_surplus",
        "correlation_id",
        existing_type=sa.Uuid(as_uuid=False),
        type_=sa.String(255),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "goal_allocation_history",
        "correlation_id",
        existing_type=sa.String(255),
        type_=sa.Uuid(as_uuid=False),
        existing_nullable=True,
    )
    op.alter_column(
        "unallocated_budget_surplus",
        "correlation_id",
        existing_type=sa.String(255),
        type_=sa.Uuid(as_uuid=False),
        existing_nullable=True,
    )
