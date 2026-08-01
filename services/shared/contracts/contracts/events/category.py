from __future__ import annotations

import re
from typing import Self
from uuid import UUID

from pydantic import model_validator

from contracts.base import BaseEvent


class _TaxonomySnapshotEvent(BaseEvent):
    """Compatibility envelope: legacy events omit canonical identity; v3 may not."""

    public_id: str | None = None
    semantic_key: str | None = None
    taxonomy_version: int | None = None
    lifecycle: str | None = None
    deprecated_in_version: int | None = None
    replaced_by_public_id: str | None = None

    @model_validator(mode="after")
    def require_v3_identity(self) -> Self:
        if self.event_version >= 3:
            missing = [
                name
                for name in ("public_id", "semantic_key", "taxonomy_version", "lifecycle")
                if getattr(self, name) is None
            ]
            if missing:
                raise ValueError(f"taxonomy v3 snapshot missing: {', '.join(missing)}")
            if UUID(self.public_id or "").version != 7:
                raise ValueError("taxonomy v3 public_id must be UUIDv7")
            if not re.fullmatch(r"[a-z][a-z0-9_]*", self.semantic_key or ""):
                raise ValueError("taxonomy v3 semantic_key must be lowercase ASCII snake_case")
            if (self.taxonomy_version or 0) < 1:
                raise ValueError("taxonomy v3 taxonomy_version must be positive")
            if self.lifecycle not in {"active", "inactive", "deprecated"}:
                raise ValueError("taxonomy v3 lifecycle is invalid")
            if self.replaced_by_public_id is not None:
                UUID(self.replaced_by_public_id)
        return self


class CategoryCreatedEvent(_TaxonomySnapshotEvent):
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
    description: str | None = None


class CategoryUpdatedEvent(_TaxonomySnapshotEvent):
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
    description: str | None = None


class CategoryDeletedEvent(_TaxonomySnapshotEvent):
    """Published when a category is removed. Carries the full final state."""

    event_type: str = "category.deleted"
    event_version: int = 2

    category_id: int
    name: str
    category_type: str
    display_order: int = 0
    description: str | None = None


class _SubCategorySnapshotEvent(_TaxonomySnapshotEvent):
    parent_public_id: str | None = None
    is_fallback: bool | None = None
    description: str | None = None

    @model_validator(mode="after")
    def require_v3_parent(self) -> Self:
        if self.event_version >= 3 and self.parent_public_id is None:
            raise ValueError("taxonomy v3 subcategory snapshot missing parent_public_id")
        if self.parent_public_id is not None and UUID(self.parent_public_id).version != 7:
            raise ValueError("taxonomy v3 parent_public_id must be UUIDv7")
        return self


class SubCategoryCreatedEvent(_SubCategorySnapshotEvent):
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


class SubCategoryUpdatedEvent(_SubCategorySnapshotEvent):
    """Published when a subcategory is modified (full current state)."""

    event_type: str = "subcategory.updated"
    event_version: int = 1

    subcategory_id: int
    name: str
    category_id: int
    is_default: bool = True


class SubCategoryDeletedEvent(_SubCategorySnapshotEvent):
    """Published when a subcategory is removed. Carries the full final state."""

    event_type: str = "subcategory.deleted"
    event_version: int = 1

    subcategory_id: int
    name: str
    category_id: int
    is_default: bool = True
