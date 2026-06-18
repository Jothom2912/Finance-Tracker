"""Add subcategory_name to transactions + backfill parent/sub split.

Revision ID: 009
Revises: 008
Create Date: 2026-06-18

Part of the category-consistency work (Fase 2).  ``category_name`` must always
hold the PARENT-level name; this adds a denormalized ``subcategory_name`` column
for the sub-level name (e.g. category_name="Mad & drikke",
subcategory_name="Dagligvarer").

The old categorized-event consumer wrote the subcategory name into
``category_name``.  After adding the column, the upgrade runs an idempotent
backfill that moves such mis-placed sub-names into ``subcategory_name`` and
restores ``category_name`` to the parent name from the local ``categories``
table.  Manually-created rows (category_name already equals the parent name)
are left untouched.

The backfill SQL is shared with ``app.maintenance.backfill_subcategory_name``
so it can also be run standalone and is covered by an integration test.

Downgrade drops the column.  The data backfill is not reversed — restoring the
parent name into ``category_name`` is the corrected state regardless, and the
moved sub-name is lost with the column.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from app.maintenance.backfill_subcategory_name import BACKFILL_SQL

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column("subcategory_name", sa.String(length=100), nullable=True),
    )
    op.execute(BACKFILL_SQL)


def downgrade() -> None:
    op.drop_column("transactions", "subcategory_name")
