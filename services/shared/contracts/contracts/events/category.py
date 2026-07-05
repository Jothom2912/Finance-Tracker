from __future__ import annotations

from contracts.base import BaseEvent


class CategoryCreatedEvent(BaseEvent):
    """Published when a new category is created.

    v2: carries full category state including ``display_order`` so
    consumers can project their read copies without extra lookups
    (self-healing, full-state convention).
    """

    event_type: str = "category.created"
    event_version: int = 2

    category_id: int
    name: str
    category_type: str
    display_order: int = 0


class CategoryUpdatedEvent(BaseEvent):
    """Published when a category is modified.

    v2: full current state only. The v1 ``previous_name``/``previous_type``
    delta fields had no consumers and are dropped — consumers upsert the
    full state instead of applying deltas.
    """

    event_type: str = "category.updated"
    event_version: int = 2

    category_id: int
    name: str
    category_type: str
    display_order: int = 0


class CategoryDeletedEvent(BaseEvent):
    """Published when a category is removed. Carries the full final state."""

    event_type: str = "category.deleted"
    event_version: int = 2

    category_id: int
    name: str
    category_type: str
    display_order: int = 0


class SubCategoryCreatedEvent(BaseEvent):
    """Published when a subcategory is created.

    Note the routing key ``subcategory.created``: a topic binding on
    ``category.*`` does NOT match it (different first word), so category
    consumers must bind ``subcategory.*`` explicitly to receive these.
    """

    event_type: str = "subcategory.created"
    event_version: int = 1

    subcategory_id: int
    name: str
    category_id: int
    is_default: bool = True


class SubCategoryUpdatedEvent(BaseEvent):
    """Published when a subcategory is modified (full current state)."""

    event_type: str = "subcategory.updated"
    event_version: int = 1

    subcategory_id: int
    name: str
    category_id: int
    is_default: bool = True


class SubCategoryDeletedEvent(BaseEvent):
    """Published when a subcategory is removed. Carries the full final state."""

    event_type: str = "subcategory.deleted"
    event_version: int = 1

    subcategory_id: int
    name: str
    category_id: int
    is_default: bool = True
