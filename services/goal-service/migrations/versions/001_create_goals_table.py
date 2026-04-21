"""Create goals table

Revision ID: 001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "goals",
        sa.Column("idGoal", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(45), nullable=True),
        sa.Column("target_amount", sa.NUMERIC(12, 2), nullable=False),
        sa.Column("current_amount", sa.NUMERIC(12, 2), nullable=False, server_default="0"),
        sa.Column("target_date", sa.Date, nullable=True),
        sa.Column("status", sa.String(45), nullable=True),
        sa.Column("Account_idAccount", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("goals")
