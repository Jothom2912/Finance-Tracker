"""Seed subcategories with pinned IDs from monolith MySQL.

Revision ID: 003
Revises: 002
Create Date: 2026-04-23

Subcategory IDs are preserved from the monolith's MySQL SubCategory table
to maintain cross-service compatibility.  transaction-service stores
subcategory_id on transactions; changing IDs would require a data migration.

IDs are derived from the monolith seed script's deterministic iteration
order over DEFAULT_TAXONOMY on a fresh MySQL database (auto-increment
starting at 1).  If the production MySQL has different IDs due to manual
modifications, update the list below from a MySQL dump before running.

Sequence is reset after seed to prevent auto-increment collisions.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: str = "002"
branch_labels: str | None = None
depends_on: str | None = None

# (id, name, category_id) — derived from DEFAULT_TAXONOMY iteration order
# on a fresh MySQL database.  Verify against production MySQL if in doubt:
#   SELECT id, name, category_id FROM SubCategory ORDER BY id;
_SUBCATEGORIES: list[tuple[int, str, int]] = [
    # Mad & drikke (category_id=1)
    (1, "Dagligvarer", 1),
    (2, "Restaurant", 1),
    (3, "Takeaway", 1),
    (4, "Kaffebar", 1),
    (5, "Kiosk", 1),
    # Bolig (category_id=2)
    (6, "Husleje", 2),
    (7, "El/vand/varme", 2),
    (8, "Forsikring", 2),
    (9, "Mobil/internet", 2),
    (10, "Vedligeholdelse", 2),
    # Transport (category_id=3)
    (11, "Offentlig transport", 3),
    (12, "Braendstof", 3),
    (13, "Bil/vedligeholdelse", 3),
    (14, "Parkering", 3),
    (15, "Cykel", 3),
    # Underholdning & fritid (category_id=4)
    (16, "Abonnementer", 4),
    (17, "Barer/natteliv", 4),
    (18, "Oplevelser", 4),
    (19, "Fitness/sport", 4),
    (20, "Sportstoj/udstyr", 4),
    # Personlig (category_id=5)
    (21, "Pleje/hygiejne", 5),
    (22, "Haarpleje", 5),
    (23, "Medicin", 5),
    (24, "Toj", 5),
    # Hjem (category_id=6)
    (25, "Mobler/DIY", 6),
    (26, "Elektronik", 6),
    # Finansielt (category_id=7)
    (27, "Gebyrer", 7),
    (28, "Renteudgifter", 7),
    (29, "Investering", 7),
    # Diverse (category_id=8)
    (30, "Kontant/ATM", 8),
    (31, "Vaskeri", 8),
    (32, "Anden", 8),
    # Indkomst (category_id=9)
    (33, "Lon", 9),
    (34, "Offentlig stotte", 9),
    (35, "Overforsel fra andre", 9),
    (36, "Renteindtaegter", 9),
    (37, "Opsparing (ind)", 9),
    # Overfoersler (category_id=10)
    (38, "MobilePay ind", 10),
    (39, "MobilePay ud", 10),
    (40, "Kontooverforsel", 10),
    (41, "Opsparing (ud)", 10),
]


def upgrade() -> None:
    bind = op.get_bind()

    for sub_id, name, category_id in _SUBCATEGORIES:
        bind.execute(
            sa.text(
                "INSERT INTO subcategories (id, name, category_id, is_default) "
                "VALUES (:id, :name, :category_id, true) "
                "ON CONFLICT (id) DO NOTHING"
            ),
            {"id": sub_id, "name": name, "category_id": category_id},
        )

    bind.execute(
        sa.text("SELECT setval('subcategories_id_seq', (SELECT COALESCE(MAX(id), 0) FROM subcategories), true)")
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text("DELETE FROM subcategories WHERE id = ANY(:ids)"),
        {"ids": [s[0] for s in _SUBCATEGORIES]},
    )
