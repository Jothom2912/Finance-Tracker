"""Add categorization metadata columns to transactions.

Revision ID: 004
Revises: 003
Create Date: 2026-04-16

Adds three nullable columns that carry the output of the monolith's
categorization pipeline (rule engine today, ML/LLM tomorrow):

- ``subcategory_id`` — FK-by-convention into the monolith's ``SubCategory``
  taxonomy.  Kept as a plain integer, without a FK constraint, because
  transaction-service does not own the subcategory table.
- ``categorization_tier`` — label identifying which pipeline step
  resolved the category (``rule``/``ml``/``llm``/``manual``/``fallback``).
- ``categorization_confidence`` — discrete confidence bucket
  (``high``/``medium``/``low``).  Kept as varchar rather than numeric
  because confidence is a categorical label in the domain model,
  not an arbitrary 0.0–1.0 float.

All three are nullable so existing rows and legacy producers remain
valid.  Column types mirror the monolith's MySQL Transaction table
exactly, so the MySQL read-model projection stays byte-for-byte
compatible.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column("subcategory_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "transactions",
        sa.Column("categorization_tier", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "transactions",
        sa.Column("categorization_confidence", sa.String(length=10), nullable=True),
    )
    op.create_index(
        "ix_transactions_subcategory_id",
        "transactions",
        ["subcategory_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_transactions_subcategory_id", table_name="transactions")
    op.drop_column("transactions", "categorization_confidence")
    op.drop_column("transactions", "categorization_tier")
    op.drop_column("transactions", "subcategory_id")
