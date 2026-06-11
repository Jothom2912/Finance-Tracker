"""Add closed_at column to monthly_budgets for idempotent month-close."""

revision = "004"
down_revision = "003"

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.add_column(
        "monthly_budgets",
        sa.Column("closed_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("monthly_budgets", "closed_at")
