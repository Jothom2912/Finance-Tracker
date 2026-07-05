"""Add subcategories read model + bootstrap seed.

Revision ID: 010
Revises: 009
Create Date: 2026-07-05

Per ADR-003, categorization-service is the sole owner of the taxonomy
and this service maintains event-synced read copies. The local
``subcategories`` table lets the write paths resolve
``subcategory_name`` and validate subcategory-belongs-to-category
without an HTTP call to categorization-service.

Bootstrap seed rationale (same as migration 005 for categories): on a
fresh compose-up, categorization-service's outbox publisher can publish
its seed events *before* this service's taxonomy consumer has declared
its queue — topic-exchange messages with no bound queue are dropped.
Seeding the canonical rows here removes that race; events keep the copy
fresh from then on. The id list is pinned to categorization-service
migration 003 (the authoritative seed).

Idempotent: ON CONFLICT (id) DO NOTHING.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "010"
down_revision: str = "009"
branch_labels: str | None = None
depends_on: str | None = None

# Pinned to categorization-service migration 003 (authoritative seed).
_SUBCATEGORIES: list[tuple[int, str, int]] = [
    (1, "Dagligvarer", 1),
    (2, "Restaurant", 1),
    (3, "Takeaway", 1),
    (4, "Kaffebar", 1),
    (5, "Kiosk", 1),
    (6, "Husleje", 2),
    (7, "El/vand/varme", 2),
    (8, "Forsikring", 2),
    (9, "Mobil/internet", 2),
    (10, "Vedligeholdelse", 2),
    (11, "Offentlig transport", 3),
    (12, "Braendstof", 3),
    (13, "Bil/vedligeholdelse", 3),
    (14, "Parkering", 3),
    (15, "Cykel", 3),
    (16, "Abonnementer", 4),
    (17, "Barer/natteliv", 4),
    (18, "Oplevelser", 4),
    (19, "Fitness/sport", 4),
    (20, "Sportstoj/udstyr", 4),
    (21, "Pleje/hygiejne", 5),
    (22, "Haarpleje", 5),
    (23, "Medicin", 5),
    (24, "Toj", 5),
    (25, "Mobler/DIY", 6),
    (26, "Elektronik", 6),
    (27, "Gebyrer", 7),
    (28, "Renteudgifter", 7),
    (29, "Investering", 7),
    (30, "Kontant/ATM", 8),
    (31, "Vaskeri", 8),
    (32, "Anden", 8),
    (33, "Lon", 9),
    (34, "Offentlig stotte", 9),
    (35, "Overforsel fra andre", 9),
    (36, "Renteindtaegter", 9),
    (37, "Opsparing (ind)", 9),
    (38, "MobilePay ind", 10),
    (39, "MobilePay ud", 10),
    (40, "Kontooverforsel", 10),
    (41, "Opsparing (ud)", 10),
]


def upgrade() -> None:
    op.create_table(
        "subcategories",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("category_id", sa.Integer, nullable=False),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_subcategories_category_id", "subcategories", ["category_id"])

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


def downgrade() -> None:
    op.drop_index("ix_subcategories_category_id", table_name="subcategories")
    op.drop_table("subcategories")
