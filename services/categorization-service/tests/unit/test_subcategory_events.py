"""Contract tests for subcategory.* events.

Verifies routing keys, versioning, and full-state round-trip so
downstream consumers (transaction-service taxonomy sync) can rely
on the schema.
"""

from __future__ import annotations

from contracts.events.category import (
    CategoryCreatedEvent,
    CategoryUpdatedEvent,
    SubCategoryCreatedEvent,
    SubCategoryDeletedEvent,
    SubCategoryUpdatedEvent,
)


class TestSubCategoryEvents:
    def test_event_types_and_versions(self) -> None:
        created = SubCategoryCreatedEvent(subcategory_id=1, name="Dagligvarer", category_id=1)
        updated = SubCategoryUpdatedEvent(subcategory_id=1, name="Dagligvarer", category_id=1)
        deleted = SubCategoryDeletedEvent(subcategory_id=1, name="Dagligvarer", category_id=1)

        assert created.event_type == "subcategory.created"
        assert updated.event_type == "subcategory.updated"
        assert deleted.event_type == "subcategory.deleted"
        assert created.event_version == 1
        assert updated.event_version == 1
        assert deleted.event_version == 1

    def test_routing_key_does_not_match_category_binding(self) -> None:
        # Topic binding `category.*` must NOT receive subcategory events;
        # the first dot-separated word differs by design.
        event = SubCategoryCreatedEvent(subcategory_id=1, name="Dagligvarer", category_id=1)
        assert not event.event_type.startswith("category.")

    def test_full_state_roundtrip(self) -> None:
        event = SubCategoryUpdatedEvent(
            subcategory_id=7,
            name="Restaurant & café",
            category_id=1,
            is_default=False,
        )
        restored = SubCategoryUpdatedEvent.from_json(event.to_json())

        assert restored.subcategory_id == 7
        assert restored.name == "Restaurant & café"
        assert restored.category_id == 1
        assert restored.is_default is False
        assert restored.correlation_id == event.correlation_id

    def test_is_default_defaults_true(self) -> None:
        event = SubCategoryCreatedEvent(subcategory_id=1, name="Dagligvarer", category_id=1)
        assert event.is_default is True


class TestCategoryEventsV2:
    def test_full_state_with_display_order(self) -> None:
        event = CategoryCreatedEvent(
            category_id=1,
            name="Mad & drikke",
            category_type="expense",
            display_order=1,
        )
        restored = CategoryCreatedEvent.from_json(event.to_json())
        assert restored.event_version == 2
        assert restored.display_order == 1

    def test_v1_payload_without_display_order_still_parses(self) -> None:
        event = CategoryUpdatedEvent(category_id=1, name="Bolig", category_type="expense")
        assert event.display_order == 0
