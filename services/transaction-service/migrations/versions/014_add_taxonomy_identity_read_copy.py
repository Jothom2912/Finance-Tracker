"""Add nullable TAX-06 canonical identity fields to taxonomy read copies.

Revision ID: 014
Revises: 013
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "014"
down_revision: str = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("categories", "subcategories"):
        op.add_column(table, sa.Column("public_id", sa.String(36), nullable=True))
        op.add_column(table, sa.Column("semantic_key", sa.String(100), nullable=True))
        op.add_column(table, sa.Column("taxonomy_version", sa.Integer(), nullable=True))
        op.add_column(table, sa.Column("lifecycle", sa.String(20), nullable=True))
        op.add_column(table, sa.Column("deprecated_in_version", sa.Integer(), nullable=True))
        op.add_column(table, sa.Column("replaced_by_public_id", sa.String(36), nullable=True))
        op.create_index(f"uq_{table}_public_id", table, ["public_id"], unique=True)
        op.create_index(f"uq_{table}_semantic_key", table, ["semantic_key"], unique=True)
    op.add_column("subcategories", sa.Column("parent_public_id", sa.String(36), nullable=True))
    op.add_column("subcategories", sa.Column("is_fallback", sa.Boolean(), nullable=True))
    op.drop_index("ix_categories_name", table_name="categories")
    op.create_index("ix_categories_name", "categories", ["name"])
    op.create_index(
        "uq_categories_active_name",
        "categories",
        ["name"],
        unique=True,
        postgresql_where=sa.text("lifecycle = 'active'"),
    )


def downgrade() -> None:
    op.drop_index("uq_categories_active_name", table_name="categories")
    op.drop_index("ix_categories_name", table_name="categories")
    op.create_index("ix_categories_name", "categories", ["name"], unique=True)
    op.drop_column("subcategories", "is_fallback")
    op.drop_column("subcategories", "parent_public_id")
    for table in ("subcategories", "categories"):
        op.drop_index(f"uq_{table}_semantic_key", table_name=table)
        op.drop_index(f"uq_{table}_public_id", table_name=table)
        for name in (
            "replaced_by_public_id",
            "deprecated_in_version",
            "lifecycle",
            "taxonomy_version",
            "semantic_key",
            "public_id",
        ):
            op.drop_column(table, name)
