"""Initial account-service schema

Revision ID: 001
Revises: None
Create Date: 2026-05-06
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "Account",
        sa.Column("idAccount", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(45), nullable=False),
        sa.Column("saldo", sa.Numeric(15, 2), nullable=False, server_default="0.00"),
        sa.Column("User_idUser", sa.Integer(), nullable=False),
        sa.Column("budget_start_day", sa.Integer(), nullable=False, server_default="1"),
        sa.PrimaryKeyConstraint("idAccount"),
    )
    op.create_index("ix_Account_User_idUser", "Account", ["User_idUser"])

    op.create_table(
        "AccountGroups",
        sa.Column("idAccountGroups", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(45), nullable=True),
        sa.Column("max_users", sa.Integer(), nullable=False, server_default="20"),
        sa.PrimaryKeyConstraint("idAccountGroups"),
    )

    op.create_table(
        "AccountGroups_has_User",
        sa.Column("AccountGroups_idAccountGroups", sa.Integer(), nullable=False),
        sa.Column("User_idUser", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("AccountGroups_idAccountGroups", "User_idUser"),
        sa.ForeignKeyConstraint(
            ["AccountGroups_idAccountGroups"],
            ["AccountGroups.idAccountGroups"],
            ondelete="CASCADE",
        ),
    )


def downgrade() -> None:
    op.drop_table("AccountGroups_has_User")
    op.drop_table("AccountGroups")
    op.drop_index("ix_Account_User_idUser", table_name="Account")
    op.drop_table("Account")
