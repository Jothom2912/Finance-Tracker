"""Add external_id + currency for idempotent bank imports.

Revision ID: 012
Revises: 011
Create Date: 2026-07-16

P2-09 (audit H10): Enable Banking delivers a stable per-transaction
identity (``entry_reference``) and a currency, but both were dropped
before import — re-sync dedup relied on the fuzzy key
``(user_id, account_id, date, amount, description)``, which wrongly
merges identical same-day purchases and duplicates rows on description
drift.

``external_id`` is exactly the "column marking a row's origin" that
migration 011's docstring said was missing: it is populated only by the
bank-sync bulk import (NULL for manual/CSV rows), so a *partial* unique
index on ``(account_id, external_id) WHERE external_id IS NOT NULL``
can enforce import idempotency without turning legitimate manual
duplicates into IntegrityErrors.  The non-unique fuzzy index from 011
stays — it still serves CSV imports and the one-time transition
fallback (matching pre-012 rows that have no external_id).
``user_id`` is not part of the key: accounts are single-owner, so
``account_id`` already scopes the reference.

The unique index doubles as the backstop for the concurrent-saga race
(two syncs passing the application-level dedup simultaneously): the
second flush raises IntegrityError, the saga step replies failure
honestly (P1-12), and the next re-sync dedupes cleanly.  Serializing
sagas per connection remains tracked as P3-14.

``currency`` is NOT NULL DEFAULT 'DKK': the whole app is implicitly
DKK today, and the server default both backfills existing rows and
keeps the manual-entry insert path unchanged.  Multi-currency display
and aggregation is F3-03.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "012"
down_revision: str = "011"
branch_labels: str | None = None
depends_on: str | None = None

_INDEX_NAME = "uq_transactions_account_external_id"


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column("external_id", sa.String(128), nullable=True),
    )
    op.add_column(
        "transactions",
        sa.Column("currency", sa.String(3), nullable=False, server_default="DKK"),
    )
    op.create_index(
        _INDEX_NAME,
        "transactions",
        ["account_id", "external_id"],
        unique=True,
        postgresql_where=sa.text("external_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(_INDEX_NAME, table_name="transactions")
    op.drop_column("transactions", "currency")
    op.drop_column("transactions", "external_id")
