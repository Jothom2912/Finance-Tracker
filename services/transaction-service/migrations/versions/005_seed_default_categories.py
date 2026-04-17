"""Seed the default Danish personal-finance category taxonomy.

Revision ID: 005
Revises: 004
Create Date: 2026-04-17

Populates ``categories`` with the ten top-level categories that the
monolith's rule-engine targets.  IDs are pinned to the values used by
the monolith MySQL ``Category`` table so that bank-sync transactions
(whose ``category_id`` is produced by the rule engine against MySQL
lookups) land on rows that actually exist in transaction-service's
Postgres.  Without this seed, fresh Postgres volumes start with an
empty ``categories`` table and the UI shows "Ukendt" for every
bank-synced transaction — an onboarding trap that produced a silent
regression during the 2026-04-17 sync before this migration existed.

Why Alembic and not the API:
    Categories are owned by transaction-service per the aggregate
    ownership model (see ``docs/retrospective-transaction-ownership.md``).
    Seeding them via Alembic makes the owning service self-sufficient:
    a fresh clone + ``alembic upgrade head`` is enough; no cross-service
    orchestration required.  Future ADR-worthy discussions about
    taxonomy changes land here as new migrations.

Idempotency:
    ``ON CONFLICT (id) DO NOTHING`` keeps the migration safe against
    pre-populated rows (e.g. existing dev environments that were
    manually back-filled before this migration existed).  The sequence
    is reset to ``MAX(id)`` after the insert so that user-created
    categories via the public API start at id=11 without colliding.

Downgrade:
    Deletes only ids 1–10.  Higher ids belong to categories created
    via the API after the seed ran and are left alone.  Any
    transactions that referenced the seed categories are orphaned
    (``category_id`` has no FK in Postgres by design — see migration
    004's note on cross-service FK-by-convention), which is consistent
    with how downgrades of data-only migrations behave elsewhere.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: str = "004"
branch_labels: str | None = None
depends_on: str | None = None


# (id, name, type) — mirrors ``DEFAULT_TAXONOMY`` in
# ``services/monolith/backend/category/domain/taxonomy.py``.  IDs are
# pinned, not auto-assigned: the rule engine uses these exact values
# and cross-service consistency depends on them.
_DEFAULT_CATEGORIES: list[tuple[int, str, str]] = [
    (1, "Mad & drikke", "expense"),
    (2, "Bolig", "expense"),
    (3, "Transport", "expense"),
    (4, "Underholdning & fritid", "expense"),
    (5, "Personlig", "expense"),
    (6, "Hjem", "expense"),
    (7, "Finansielt", "expense"),
    (8, "Diverse", "expense"),
    (9, "Indkomst", "income"),
    (10, "Overfoersler", "transfer"),
]


def upgrade() -> None:
    bind = op.get_bind()

    insert_stmt = sa.text(
        "INSERT INTO categories (id, name, type) "
        "VALUES (:id, :name, :type) "
        "ON CONFLICT (id) DO NOTHING"
    )
    for cat_id, name, type_ in _DEFAULT_CATEGORIES:
        bind.execute(insert_stmt, {"id": cat_id, "name": name, "type": type_})

    bind.execute(
        sa.text(
            "SELECT setval("
            "  'categories_id_seq', "
            "  (SELECT COALESCE(MAX(id), 0) FROM categories), "
            "  true"
            ")"
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    seeded_ids = [cat_id for cat_id, _, _ in _DEFAULT_CATEGORIES]
    bind.execute(
        sa.text("DELETE FROM categories WHERE id = ANY(:ids)"),
        {"ids": seeded_ids},
    )
