"""Add transactions.deleted_at — soft-delete for the audit trail.

Revision ID: 013
Revises: 012
Create Date: 2026-07-28

P2-25/P3-37: ``DELETE /api/v1/transactions/{id}`` hard-deleted the row,
against the project's own anti-pattern list, and left the
``transaction.categorized`` consumer unable to tell "not committed yet"
(retry is right) from "gone forever" (retry is pointless) — the observed
DLQ bug in ``transaction_service.transaction_categorized.dlq``.  The
column is what makes that branch expressible at all; see
``dev-notes/decisions/2026-07-28-transaction-soft-delete.md``.

The partial unique index from 012 is recreated with ``AND deleted_at IS
NULL``.  Without that, a tombstone keeps occupying its
``(account_id, external_id)`` slot and re-importing an id-bearing row
after a delete hits a unique violation that looks like a saga failure.
Decision 1 in the note: a soft-deleted row must not block re-import.

``downgrade`` is not free of consequence and can fail loudly: rows soft-
deleted in the meantime become visible again, and if any of them was
re-imported under the same ``(account_id, external_id)`` the narrower
index cannot be rebuilt.  That is the honest signal — resolve the
duplicates by hand rather than widening the index back silently.

``CREATE INDEX CONCURRENTLY`` is deliberately NOT used here.  On the
current volume (low thousands) the drop+create is irrelevant, and
CONCURRENTLY cannot run inside Alembic's transaction.  If this ever runs
against a real production-sized ``transactions``, split it out and take
the index non-transactionally — noted here rather than left to be
rediscovered.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "013"
down_revision: str = "012"
branch_labels: str | None = None
depends_on: str | None = None

_INDEX_NAME = "uq_transactions_account_external_id"
_INDEX_COLUMNS = ["account_id", "external_id"]


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.drop_index(_INDEX_NAME, table_name="transactions")
    op.create_index(
        _INDEX_NAME,
        "transactions",
        _INDEX_COLUMNS,
        unique=True,
        postgresql_where=sa.text("external_id IS NOT NULL AND deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(_INDEX_NAME, table_name="transactions")
    op.create_index(
        _INDEX_NAME,
        "transactions",
        _INDEX_COLUMNS,
        unique=True,
        postgresql_where=sa.text("external_id IS NOT NULL"),
    )
    op.drop_column("transactions", "deleted_at")
