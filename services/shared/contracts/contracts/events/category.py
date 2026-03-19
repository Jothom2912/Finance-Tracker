from __future__ import annotations

from contracts.base import BaseEvent


class CategoryCreatedEvent(BaseEvent):
    """Published when a new category is created."""

    event_type: str = "category.created"
    event_version: int = 1

    category_id: int
    name: str
    category_type: str


class CategoryUpdatedEvent(BaseEvent):
    """Published when a category is modified.

    Carries both current and previous values so downstream consumers
    can update their local copies without extra lookups.
    """

    event_type: str = "category.updated"
    event_version: int = 1

    category_id: int
    name: str
    category_type: str
    previous_name: str
    previous_type: str


class CategoryDeletedEvent(BaseEvent):
    """Published when a category is removed."""

    event_type: str = "category.deleted"
    event_version: int = 1

    category_id: int
    name: str
    category_type: str
