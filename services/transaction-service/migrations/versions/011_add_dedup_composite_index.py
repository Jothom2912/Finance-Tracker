"""Add composite index on the import dedup key.

Revision ID: 011
Revises: 010
Create Date: 2026-07-14

The CSV/bulk import paths deduplicate on the cross-service key
``(user_id, account_id, date, amount, description)`` (H15).  The batch
anti-join in ``find_existing_dedup_keys`` filters on the leading four
columns; this composite index serves that lookup instead of the
single-column ``user_id`` index + heap filters.  ``description`` is
included so the full key can be resolved index-only.

Deliberately NOT unique (not even partial): two transactions with an
identical key are legitimate outside the import paths — a user manually
entering two identical purchases on the same day, or a bank statement
genuinely containing two identical rows.  The table has no column
marking a row's origin, so no partial-index predicate can scope
uniqueness to imported rows only.  A unique index would therefore turn
legitimate writes into IntegrityErrors.  The (accepted) residual risk
is the concurrent-import race, mitigated upstream by saga-level
serialization of bank syncs.
"""

from __future__ import annotations

from alembic import op

revision: str = "011"
down_revision: str = "010"
branch_labels: str | None = None
depends_on: str | None = None

_INDEX_NAME = "ix_transactions_dedup_key"


def upgrade() -> None:
    op.create_index(
        _INDEX_NAME,
        "transactions",
        ["user_id", "account_id", "date", "amount", "description"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(_INDEX_NAME, table_name="transactions")
