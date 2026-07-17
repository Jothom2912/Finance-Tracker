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


# batch_alter_table: no-op wrapper on Postgres (plain ALTER), table-recreate on
# sqlite, hvor ALTER COLUMN ... TYPE ikke findes — migrations-testsuiten kører
# mod sqlite (se finding F-2026-07-12-01).
_TABLES = ("goal_allocation_history", "unallocated_budget_surplus")


def upgrade() -> None:
    for table in _TABLES:
        with op.batch_alter_table(table) as batch:
            batch.alter_column(
                "correlation_id",
                existing_type=sa.Uuid(as_uuid=False),
                type_=sa.String(255),
                existing_nullable=True,
            )


def downgrade() -> None:
    # postgresql_using: Postgres kan ikke auto-caste varchar→uuid. Casten
    # fejler bevidst højlydt hvis kolonnen indeholder ikke-UUID source_keys —
    # downgrade er kun mulig før deterministiske nøgler er skrevet.
    for table in _TABLES:
        with op.batch_alter_table(table) as batch:
            batch.alter_column(
                "correlation_id",
                existing_type=sa.String(255),
                type_=sa.Uuid(as_uuid=False),
                existing_nullable=True,
                postgresql_using="correlation_id::uuid",
            )
