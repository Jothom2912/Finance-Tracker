"""create goals table

Revision ID: 001
Revises:
Create Date: 2026-04-30 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "goals",
        sa.Column("idGoal", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=45), nullable=True),
        sa.Column("target_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("current_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("target_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=45), nullable=True),
        sa.Column("Account_idAccount", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_goals_Account_idAccount", "goals", ["Account_idAccount"])


def downgrade() -> None:
    op.drop_index("ix_goals_Account_idAccount", table_name="goals")
    op.drop_table("goals")
