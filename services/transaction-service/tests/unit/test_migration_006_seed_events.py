"""Unit tests for migration 006's ``build_seed_events`` pure function.

The migration itself isn't exercised here — Alembic's runtime
integration with Postgres is out of scope for a unit test and would
require Testcontainers.  What we *can* lock down without a database:

* Determinism — running the generator twice must produce identical
  output, including the derived UUIDs.  This is what makes the
  migration safely idempotent via ``ON CONFLICT (id) DO NOTHING``.
* Payload contract — each ``payload_json`` must round-trip through
  ``CategoryCreatedEvent.model_validate_json`` so a future required
  field on the event contract breaks the seed loudly rather than
  silently producing payloads the consumer rejects at runtime.
* Uniqueness — all ten outbox ``id`` values must be distinct so the
  insert doesn't silently collapse two seed categories into one
  surviving event.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from contracts.events.category import CategoryCreatedEvent

# Migration filenames start with a digit, so the module can't be
# imported via ``from migrations.versions import ...``.  Load by file
# path instead.
_MIGRATION_PATH = (
    Path(__file__).resolve().parents[2] / "migrations" / "versions" / "006_emit_default_category_events.py"
)
_spec = importlib.util.spec_from_file_location("migration_006", _MIGRATION_PATH)
assert _spec is not None and _spec.loader is not None
migration_006 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(migration_006)


def test_build_seed_events_returns_ten_rows() -> None:
    rows = migration_006.build_seed_events()
    assert len(rows) == 10


def test_build_seed_events_is_deterministic() -> None:
    first = migration_006.build_seed_events()
    second = migration_006.build_seed_events()
    assert first == second, (
        "build_seed_events must be deterministic so the migration's "
        "ON CONFLICT(id) idempotency holds across repeated upgrades."
    )


def test_build_seed_events_outbox_ids_are_unique() -> None:
    rows = migration_006.build_seed_events()
    ids = [row["id"] for row in rows]
    assert len(set(ids)) == len(ids), (
        "Outbox row IDs must be unique, otherwise ON CONFLICT would "
        "collapse distinct seed categories into a single surviving event."
    )


def test_build_seed_events_correlation_ids_are_unique() -> None:
    rows = migration_006.build_seed_events()
    correlation_ids = [row["correlation_id"] for row in rows]
    assert len(set(correlation_ids)) == len(correlation_ids)


def test_build_seed_events_payload_validates_as_category_created_event() -> None:
    """A future required field on CategoryCreatedEvent must break this
    test — that's the whole point of round-tripping through Pydantic.
    """
    for row in migration_006.build_seed_events():
        event = CategoryCreatedEvent.model_validate_json(row["payload_json"])
        assert event.event_type == "category.created"
        assert event.category_id == int(row["aggregate_id"])


def test_build_seed_events_covers_expected_category_ids() -> None:
    rows = migration_006.build_seed_events()
    aggregate_ids = sorted(int(row["aggregate_id"]) for row in rows)
    assert aggregate_ids == list(range(1, 11))


def test_build_seed_events_transfer_type_survives_roundtrip() -> None:
    """The ``transfer`` category type was added to the enum in the
    same PR as this migration — regression-guard to prove the payload
    carries it unchanged.
    """
    rows = migration_006.build_seed_events()
    by_id = {int(row["aggregate_id"]): row for row in rows}
    payload = json.loads(by_id[10]["payload_json"])
    assert payload["name"] == "Overfoersler"
    assert payload["category_type"] == "transfer"
