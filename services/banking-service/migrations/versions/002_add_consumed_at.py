"""Add consumed_at column to pending_authorizations.

Revision ID: 002
Revises: 001
Create Date: 2026-06-12
"""

from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pending_authorizations",
        sa.Column("consumed_at", sa.DateTime, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("pending_authorizations", "consumed_at")
