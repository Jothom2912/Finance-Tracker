"""Heal display_order drift + emit full-state taxonomy seed events.

Revision ID: 006
Revises: 005
Create Date: 2026-07-05

Part of ADR-003 (taxonomy ownership consolidated into this service).
Two concerns, both idempotent:

1. **Heal ``display_order`` drift.**  The (now removed)
   ``CategorySyncConsumer`` upserted categories from transaction-service
   events without setting ``display_order``, so existing dev DBs where
   the seed rows arrived via events have ``display_order = 0`` for all
   ten defaults.  We restore the canonical ordering from migration 002,
   but only for rows still at 0 — a deliberate user change survives.

2. **Re-announce the seed taxonomy via the outbox.**  transaction-service
   now maintains event-synced read copies of ``categories`` and
   ``subcategories``.  Existing dev DBs never saw ``category.created``
   v2 / ``subcategory.created`` events from this service (the old owner
   emitted v1 category events only), so we insert one outbox row per
   seed category and subcategory.  Consumers upsert idempotently, so
   re-announcing state they already have is harmless.

Design copied from transaction-service migration 006 (the previous
owner's event-seed migration):

* Deterministic UUIDv5 outbox ids/correlation ids — running upgrade
  twice produces identical rows and ``ON CONFLICT (id) DO NOTHING``
  skips them.
* Fixed event timestamp so ``payload_json`` is byte-identical across
  runs (unit-testable, diff-friendly).
* Real Pydantic event classes, not hand-rolled JSON — a future
  required contract field breaks this migration at construction time
  instead of silently at the consumer.

Downgrade removes only the outbox rows this migration owns; already
published events are not retracted, and display_order healing is not
reverted (there is no record of the pre-heal drift).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op
from contracts.events.category import CategoryCreatedEvent, SubCategoryCreatedEvent

revision: str = "006"
down_revision: str = "005"
branch_labels: str | None = None
depends_on: str | None = None

# Duplicated from migrations 002/003 on purpose — coupling via a shared
# import would make downgrade-then-upgrade of one file depend on the other.
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

_SEED_NAMESPACE = uuid.NAMESPACE_DNS
_SEED_TIMESTAMP = datetime(2026, 7, 5, 0, 0, 0, tzinfo=timezone.utc)


def build_seed_events() -> list[dict[str, str]]:
    """Pure function returning the outbox rows upgrade() inserts.

    No database access — determinism and payload shape are unit-tested
    without Postgres.
    """
    rows: list[dict[str, str]] = []

    for cat_id, name, type_, display_order in _DEFAULT_CATEGORIES:
        outbox_id = str(
            uuid.uuid5(_SEED_NAMESPACE, f"categorization-service.seed.006.outbox.category.{cat_id}")
        )
        correlation_id = str(
            uuid.uuid5(_SEED_NAMESPACE, f"categorization-service.seed.006.correlation.category.{cat_id}")
        )
        event = CategoryCreatedEvent(
            category_id=cat_id,
            name=name,
            category_type=type_,
            display_order=display_order,
            correlation_id=correlation_id,
            timestamp=_SEED_TIMESTAMP,
        )
        rows.append(
            {
                "id": outbox_id,
                "aggregate_type": "category",
                "aggregate_id": str(cat_id),
                "event_type": event.event_type,
                "payload_json": event.to_json(),
                "correlation_id": correlation_id,
            }
        )

    for sub_id, name, category_id in _SUBCATEGORIES:
        outbox_id = str(
            uuid.uuid5(_SEED_NAMESPACE, f"categorization-service.seed.006.outbox.subcategory.{sub_id}")
        )
        correlation_id = str(
            uuid.uuid5(_SEED_NAMESPACE, f"categorization-service.seed.006.correlation.subcategory.{sub_id}")
        )
        event = SubCategoryCreatedEvent(
            subcategory_id=sub_id,
            name=name,
            category_id=category_id,
            is_default=True,
            correlation_id=correlation_id,
            timestamp=_SEED_TIMESTAMP,
        )
        rows.append(
            {
                "id": outbox_id,
                "aggregate_type": "subcategory",
                "aggregate_id": str(sub_id),
                "event_type": event.event_type,
                "payload_json": event.to_json(),
                "correlation_id": correlation_id,
            }
        )

    return rows


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Heal display_order drift (only rows still at the consumer default 0).
    for cat_id, _name, _type, display_order in _DEFAULT_CATEGORIES:
        bind.execute(
            sa.text(
                "UPDATE categories SET display_order = :display_order "
                "WHERE id = :id AND display_order = 0"
            ),
            {"id": cat_id, "display_order": display_order},
        )

    # 2. Re-announce seed taxonomy via the outbox.
    stmt = sa.text(
        "INSERT INTO outbox_events ("
        "  id, aggregate_type, aggregate_id, event_type, payload_json, "
        "  correlation_id, status, attempts"
        ") VALUES ("
        "  :id, :aggregate_type, :aggregate_id, :event_type, :payload_json, "
        "  :correlation_id, 'pending', 0"
        ") ON CONFLICT (id) DO NOTHING"
    )
    for row in build_seed_events():
        bind.execute(stmt, row)


def downgrade() -> None:
    bind = op.get_bind()
    ids = [row["id"] for row in build_seed_events()]
    bind.execute(
        sa.text("DELETE FROM outbox_events WHERE id = ANY(:ids)"),
        {"ids": ids},
    )
