"""Seed merchants from SEED_MERCHANT_MAPPINGS.

Revision ID: 004
Revises: 003
Create Date: 2026-04-23

Each keyword in SEED_MERCHANT_MAPPINGS becomes one merchant row.
IDs are auto-generated (no external references to merchant IDs exist).
Resolves subcategory_id by name lookup against the seeded subcategories.

Idempotent: ON CONFLICT (normalized_name) DO NOTHING.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: str = "003"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    from app.domain.taxonomy import SEED_MERCHANT_MAPPINGS

    bind = op.get_bind()

    rows = bind.execute(sa.text("SELECT id, name FROM subcategories"))
    sub_lookup: dict[str, int] = {row.name: row.id for row in rows}

    for keyword, mapping in SEED_MERCHANT_MAPPINGS.items():
        sub_name = mapping["subcategory"]
        display_name = mapping["display"]
        sub_id = sub_lookup.get(sub_name)

        if sub_id is None:
            continue

        bind.execute(
            sa.text(
                "INSERT INTO merchants (normalized_name, display_name, subcategory_id) "
                "VALUES (:normalized_name, :display_name, :subcategory_id) "
                "ON CONFLICT (normalized_name) DO NOTHING"
            ),
            {
                "normalized_name": keyword.lower(),
                "display_name": display_name,
                "subcategory_id": sub_id,
            },
        )


def downgrade() -> None:
    from app.domain.taxonomy import SEED_MERCHANT_MAPPINGS

    bind = op.get_bind()
    keywords = [kw.lower() for kw in SEED_MERCHANT_MAPPINGS]
    bind.execute(
        sa.text("DELETE FROM merchants WHERE normalized_name = ANY(:names)"),
        {"names": keywords},
    )
