"""Emit ``CategoryCreatedEvent`` for the default seed taxonomy.

Revision ID: 006
Revises: 005
Create Date: 2026-04-17

Migration 005 inserted the ten default categories as pure data rows.
Projections in other services (monolith MySQL ``Category`` via
``CategorySyncConsumer``) only learn about them via RabbitMQ events,
so a pure data-seed leaves the downstream projection empty.  This
migration closes that gap by writing one outbox row per seed category
so the transactional outbox worker publishes ``category.created``
events on its next poll.

Design choices:

* **Split from 005.**  Migration 005 is pure data; 006 is the event
  emission of that data.  Separating them means either migration can
  be rolled forward/back independently, and the semantic intent of
  each file stays narrow enough to understand in isolation.
* **Deterministic UUIDs (v5).**  The outbox row ``id`` and the event
  ``correlation_id`` are derived from a fixed namespace + the
  category id.  Idempotency comes from the ID being a pure function
  of the seed content — running ``upgrade`` twice produces the same
  UUIDs, ``ON CONFLICT (id) DO NOTHING`` skips the duplicates, and
  we don't need an extra composite unique constraint on the outbox
  table just for this one use case.
* **Fixed event timestamp.**  ``BaseEvent.timestamp`` normally
  defaults to ``datetime.now(UTC)``.  For seed events we override it
  with a fixed value so the ``payload_json`` is byte-identical across
  migration runs — which matters both for unit-testing the seed
  generator and for debugging (a diff between two environments
  doesn't show spurious timestamp drift).
* **Pydantic, not hand-rolled JSON.**  We instantiate the real
  ``CategoryCreatedEvent`` class and call ``model_dump_json()``.  If
  the event contract gains a required field later, this migration
  fails at import/construction time, *not* silently at runtime when
  the consumer receives it.

Idempotency guarantee:
    ``upgrade`` can be run any number of times against the same DB
    without producing duplicate outbox rows.  The only state-visible
    difference across runs is that rows already marked ``published``
    stay ``published`` — we do not reset their status.

Downgrade:
    Removes only the ten outbox rows this migration owns (looked up
    by their deterministic UUIDs).  If the outbox worker has already
    published them, the downstream MySQL projection is unaffected —
    events don't get retracted.  This is consistent with how every
    other event-emitting migration behaves.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op
from contracts.events.category import CategoryCreatedEvent

revision: str = "006"
down_revision: str = "005"
branch_labels: str | None = None
depends_on: str | None = None


# Duplicated from migration 005 on purpose.  Coupling the two via a
# shared import would make downgrade-then-upgrade of just one of them
# depend on the other, which defeats the split.
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

# Stable namespace for UUIDv5 derivation.  Using NAMESPACE_DNS with a
# fully-qualified seed string is a common convention and keeps us from
# inventing a new magic UUID that future readers have to trust.
_SEED_NAMESPACE = uuid.NAMESPACE_DNS

# Fixed point-in-time for payload reproducibility.  The exact value
# doesn't matter — only that it's constant across runs.
_SEED_TIMESTAMP = datetime(2026, 4, 17, 0, 0, 0, tzinfo=timezone.utc)


def build_seed_events() -> list[dict[str, str]]:
    """Return the outbox rows that upgrade() will insert.

    Exposed as a pure function with no database access so the
    determinism and payload shape can be unit-tested without spinning
    up Postgres.  The return shape matches the ``outbox_events`` table
    columns needed for ``INSERT``.
    """
    rows: list[dict[str, str]] = []
    for cat_id, name, type_ in _DEFAULT_CATEGORIES:
        outbox_id = str(
            uuid.uuid5(
                _SEED_NAMESPACE,
                f"transaction-service.seed.006.outbox.{cat_id}",
            )
        )
        correlation_id = str(
            uuid.uuid5(
                _SEED_NAMESPACE,
                f"transaction-service.seed.006.correlation.{cat_id}",
            )
        )
        event = CategoryCreatedEvent(
            category_id=cat_id,
            name=name,
            category_type=type_,
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
    return rows


def upgrade() -> None:
    bind = op.get_bind()
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
