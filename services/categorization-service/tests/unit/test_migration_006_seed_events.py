"""Unit tests for migration 006's ``build_seed_events`` pure function.

Same rationale as transaction-service's seed-event test: without a
database we lock down determinism (idempotency via ON CONFLICT depends
on it), payload contract validity, and id uniqueness.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from contracts.events.category import CategoryCreatedEvent, SubCategoryCreatedEvent

# Migration filenames start with a digit — load by file path.
_MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "migrations"
    / "versions"
    / "006_heal_display_order_and_emit_taxonomy_seed_events.py"
)
_spec = importlib.util.spec_from_file_location("cat_migration_006", _MIGRATION_PATH)
assert _spec is not None and _spec.loader is not None
migration_006 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(migration_006)


def _rows() -> list[dict[str, str]]:
    return migration_006.build_seed_events()


def test_row_count_is_ten_categories_plus_41_subcategories() -> None:
    rows = _rows()
    categories = [r for r in rows if r["aggregate_type"] == "category"]
    subcategories = [r for r in rows if r["aggregate_type"] == "subcategory"]
    assert len(categories) == 10
    assert len(subcategories) == 41


def test_build_seed_events_is_deterministic() -> None:
    assert _rows() == _rows(), (
        "build_seed_events must be deterministic so ON CONFLICT(id) idempotency holds across repeated upgrades."
    )


def test_outbox_and_correlation_ids_are_unique() -> None:
    rows = _rows()
    ids = [r["id"] for r in rows]
    correlation_ids = [r["correlation_id"] for r in rows]
    assert len(set(ids)) == len(ids)
    assert len(set(correlation_ids)) == len(correlation_ids)


def test_category_payloads_validate_and_carry_display_order() -> None:
    for row in (r for r in _rows() if r["aggregate_type"] == "category"):
        event = CategoryCreatedEvent.model_validate_json(row["payload_json"])
        assert event.event_type == "category.created"
        assert event.event_version == 2
        assert event.category_id == int(row["aggregate_id"])
        assert event.display_order > 0, "seed events must carry the canonical ordering"


def test_subcategory_payloads_validate_as_full_state() -> None:
    for row in (r for r in _rows() if r["aggregate_type"] == "subcategory"):
        event = SubCategoryCreatedEvent.model_validate_json(row["payload_json"])
        assert event.event_type == "subcategory.created"
        assert event.subcategory_id == int(row["aggregate_id"])
        assert event.is_default is True
        assert 1 <= event.category_id <= 10


def test_routing_keys_match_event_types() -> None:
    rows = _rows()
    assert {r["event_type"] for r in rows} == {"category.created", "subcategory.created"}


def test_fallback_anden_is_seeded() -> None:
    by_id = {
        int(r["aggregate_id"]): json.loads(r["payload_json"]) for r in _rows() if r["aggregate_type"] == "subcategory"
    }
    assert by_id[32]["name"] == "Anden"
    assert by_id[32]["category_id"] == 8
