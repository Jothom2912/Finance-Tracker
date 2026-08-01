from __future__ import annotations

import pytest
from contracts.events.category import CategoryCreatedEvent, SubCategoryCreatedEvent
from pydantic import ValidationError

PUBLIC_ID = "019fba9e-d800-7d31-8208-aeddb2226b0f"
PARENT_ID = "019fba9e-d800-7500-9234-123456789abc"


def test_legacy_taxonomy_payload_remains_accepted() -> None:
    event = CategoryCreatedEvent(category_id=1, name="Legacy", category_type="expense")
    assert event.event_version == 2
    assert event.public_id is None


def test_v3_requires_complete_canonical_identity() -> None:
    with pytest.raises(ValidationError, match="taxonomy v3 snapshot missing"):
        CategoryCreatedEvent(event_version=3, category_id=11, name="Food", category_type="expense")


def test_v3_subcategory_requires_parent_identity() -> None:
    with pytest.raises(ValidationError, match="parent_public_id"):
        SubCategoryCreatedEvent(
            event_version=3,
            subcategory_id=42,
            category_id=11,
            name="Groceries",
            public_id=PUBLIC_ID,
            semantic_key="groceries",
            taxonomy_version=1,
            lifecycle="active",
        )

    event = SubCategoryCreatedEvent(
        event_version=3,
        subcategory_id=42,
        category_id=11,
        name="Groceries",
        public_id=PUBLIC_ID,
        semantic_key="groceries",
        parent_public_id=PARENT_ID,
        taxonomy_version=1,
        lifecycle="active",
        is_fallback=False,
    )
    assert event.event_version == 3
