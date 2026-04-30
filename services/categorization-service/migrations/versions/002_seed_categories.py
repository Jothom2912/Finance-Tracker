"""Seed the 10 default categories with pinned IDs.

Revision ID: 002
Revises: 001
Create Date: 2026-04-23

IDs 1-10 are pinned to match transaction-service's migration 005 and
the monolith's MySQL Category projection.  This ensures cross-service
ID compatibility without a mapping table.

Idempotent: ON CONFLICT (id) DO NOTHING.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: str = "001"
branch_labels: str | None = None
depends_on: str | None = None

_DEFAULT_CATEGORIES: list[tuple[int, str, str, int]] = [
    (1, "Mad & drikke", "expense", 1),
    (2, "Bolig", "expense", 2),
    (3, "Transport", "expense", 3),
    (4, "Underholdning & fritid", "expense", 4),
    (5, "Personlig", "expense", 5),
    (6, "Hjem", "expense", 6),
    (7, "Finansielt", "expense", 7),
    (8, "Diverse", "expense", 8),
    (9, "Indkomst", "income", 10),
    (10, "Overfoersler", "transfer", 20),
]


def upgrade() -> None:
    bind = op.get_bind()

    for cat_id, name, cat_type, display_order in _DEFAULT_CATEGORIES:
        bind.execute(
            sa.text(
                "INSERT INTO categories (id, name, type, display_order) "
                "VALUES (:id, :name, :type, :display_order) "
                "ON CONFLICT (id) DO NOTHING"
            ),
            {"id": cat_id, "name": name, "type": cat_type, "display_order": display_order},
        )

    bind.execute(sa.text("SELECT setval('categories_id_seq', (SELECT COALESCE(MAX(id), 0) FROM categories), true)"))


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text("DELETE FROM categories WHERE id = ANY(:ids)"),
        {"ids": [c[0] for c in _DEFAULT_CATEGORIES]},
    )
