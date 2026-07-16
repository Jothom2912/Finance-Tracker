"""CategoryService — CRUD for taxonomy (categories + subcategories).

This service owns the master category data and emits category.* and
subcategory.* events via the transactional outbox for downstream
consumers (per ADR-003, categorization-service is the sole taxonomy
writer; transaction-service keeps event-synced read copies).
"""

from __future__ import annotations

import logging

from contracts.events.category import (
    CategoryCreatedEvent,
    CategoryDeletedEvent,
    CategoryUpdatedEvent,
    SubCategoryCreatedEvent,
    SubCategoryDeletedEvent,
    SubCategoryUpdatedEvent,
)

from app.application.dto import (
    CategoryResponseDTO,
    CreateCategoryDTO,
    CreateSubCategoryDTO,
    SubCategoryResponseDTO,
    UpdateCategoryDTO,
    UpdateSubCategoryDTO,
)
from app.application.ports.outbound import IUnitOfWork
from app.domain.entities import SubCategory
from app.domain.exceptions import (
    CategoryHasSubcategories,
    CategoryNotFound,
    DuplicateCategoryName,
    DuplicateSubCategoryName,
    InvalidCategoryType,
    SubCategoryInUse,
    SubCategoryNotFound,
)
from app.domain.value_objects import CategoryType

logger = logging.getLogger(__name__)

# The rule engine's absolute fallback resolves the subcategory literally
# named "Anden" (see transaction_consumer._build_rule_engine). Deleting it
# would silently break fallback categorization.
FALLBACK_SUBCATEGORY_NAME = "Anden"


def _parse_category_type(value: str) -> CategoryType:
    try:
        return CategoryType(value)
    except ValueError as exc:
        raise InvalidCategoryType(value) from exc


class CategoryService:
    def __init__(self, uow: IUnitOfWork) -> None:
        self._uow = uow

    # ── Categories ──

    async def create_category(self, dto: CreateCategoryDTO) -> CategoryResponseDTO:
        category_type = _parse_category_type(dto.type)
        async with self._uow:
            existing = await self._uow.categories.find_by_name(dto.name)
            if existing is not None:
                raise DuplicateCategoryName(dto.name)

            category = await self._uow.categories.create(
                dto.name,
                category_type,
                display_order=dto.display_order,
            )

            await self._uow.outbox.add(
                event=CategoryCreatedEvent(
                    category_id=category.id,
                    name=category.name,
                    category_type=category.type.value,
                    display_order=category.display_order,
                ),
                aggregate_type="category",
                aggregate_id=str(category.id),
            )
            await self._uow.commit()
            return self._to_dto(category)

    async def list_categories(self) -> list[CategoryResponseDTO]:
        async with self._uow:
            categories = await self._uow.categories.find_all()
            return [self._to_dto(c) for c in categories]

    async def get_category(self, category_id: int) -> CategoryResponseDTO:
        async with self._uow:
            category = await self._uow.categories.find_by_id(category_id)
            if category is None:
                raise CategoryNotFound(category_id)
            return self._to_dto(category)

    async def update_category(self, category_id: int, dto: UpdateCategoryDTO) -> CategoryResponseDTO:
        async with self._uow:
            existing = await self._uow.categories.find_by_id(category_id)
            if existing is None:
                raise CategoryNotFound(category_id)

            fields: dict[str, object] = {}
            if dto.name is not None:
                fields["name"] = dto.name
            if dto.type is not None:
                fields["type"] = _parse_category_type(dto.type)
            if dto.display_order is not None:
                fields["display_order"] = dto.display_order

            if not fields:
                return self._to_dto(existing)

            if dto.name is not None and dto.name != existing.name:
                duplicate = await self._uow.categories.find_by_name(dto.name)
                if duplicate is not None:
                    raise DuplicateCategoryName(dto.name)

            updated = await self._uow.categories.update(category_id, **fields)

            await self._uow.outbox.add(
                event=CategoryUpdatedEvent(
                    category_id=updated.id,
                    name=updated.name,
                    category_type=updated.type.value if hasattr(updated.type, "value") else str(updated.type),
                    display_order=getattr(updated, "display_order", 0),
                ),
                aggregate_type="category",
                aggregate_id=str(updated.id),
            )
            await self._uow.commit()
            return self._to_dto(updated)

    async def delete_category(self, category_id: int) -> None:
        async with self._uow:
            existing = await self._uow.categories.find_by_id(category_id)
            if existing is None:
                raise CategoryNotFound(category_id)

            subcategories = await self._uow.subcategories.find_by_category_id(category_id)
            if subcategories:
                raise CategoryHasSubcategories(category_id, len(subcategories))

            await self._uow.categories.delete(category_id)

            await self._uow.outbox.add(
                event=CategoryDeletedEvent(
                    category_id=existing.id,
                    name=existing.name,
                    category_type=existing.type.value if hasattr(existing.type, "value") else str(existing.type),
                    display_order=getattr(existing, "display_order", 0),
                ),
                aggregate_type="category",
                aggregate_id=str(existing.id),
            )
            await self._uow.commit()

    # ── Subcategories ──

    async def list_subcategories(self, category_id: int) -> list[SubCategoryResponseDTO]:
        async with self._uow:
            category = await self._uow.categories.find_by_id(category_id)
            if category is None:
                raise CategoryNotFound(category_id)
            subs = await self._uow.subcategories.find_by_category_id(category_id)
            return [self._to_sub_dto(s) for s in subs]

    async def list_all_subcategories(self) -> list[SubCategoryResponseDTO]:
        async with self._uow:
            subs = await self._uow.subcategories.find_all()
            return [self._to_sub_dto(s) for s in subs]

    async def create_subcategory(
        self,
        category_id: int,
        dto: CreateSubCategoryDTO,
    ) -> SubCategoryResponseDTO:
        async with self._uow:
            category = await self._uow.categories.find_by_id(category_id)
            if category is None:
                raise CategoryNotFound(category_id)

            duplicate = await self._uow.subcategories.find_by_name_and_category(dto.name, category_id)
            if duplicate is not None:
                raise DuplicateSubCategoryName(dto.name)

            # User-created subcategories are not part of the seeded default
            # taxonomy — mark them so seeds can be distinguished later.
            sub = await self._uow.subcategories.create(dto.name, category_id, is_default=False)

            await self._uow.outbox.add(
                event=SubCategoryCreatedEvent(
                    subcategory_id=sub.id,
                    name=sub.name,
                    category_id=sub.category_id,
                    is_default=sub.is_default,
                ),
                aggregate_type="subcategory",
                aggregate_id=str(sub.id),
            )
            await self._uow.commit()
            return self._to_sub_dto(sub)

    async def update_subcategory(
        self,
        subcategory_id: int,
        dto: UpdateSubCategoryDTO,
    ) -> SubCategoryResponseDTO:
        async with self._uow:
            existing = await self._uow.subcategories.find_by_id(subcategory_id)
            if existing is None:
                raise SubCategoryNotFound(subcategory_id)

            target_category_id = dto.category_id if dto.category_id is not None else existing.category_id
            target_name = dto.name if dto.name is not None else existing.name

            if dto.category_id is not None and dto.category_id != existing.category_id:
                parent = await self._uow.categories.find_by_id(dto.category_id)
                if parent is None:
                    raise CategoryNotFound(dto.category_id)

            fields: dict[str, object] = {}
            if dto.name is not None:
                fields["name"] = dto.name
            if dto.category_id is not None:
                fields["category_id"] = dto.category_id

            if not fields:
                return self._to_sub_dto(existing)

            if (target_name, target_category_id) != (existing.name, existing.category_id):
                duplicate = await self._uow.subcategories.find_by_name_and_category(
                    target_name,
                    target_category_id,
                )
                if duplicate is not None and duplicate.id != subcategory_id:
                    raise DuplicateSubCategoryName(target_name)

            updated = await self._uow.subcategories.update(subcategory_id, **fields)

            await self._uow.outbox.add(
                event=SubCategoryUpdatedEvent(
                    subcategory_id=updated.id,
                    name=updated.name,
                    category_id=updated.category_id,
                    is_default=updated.is_default,
                ),
                aggregate_type="subcategory",
                aggregate_id=str(updated.id),
            )
            await self._uow.commit()
            return self._to_sub_dto(updated)

    async def delete_subcategory(self, subcategory_id: int) -> None:
        async with self._uow:
            existing = await self._uow.subcategories.find_by_id(subcategory_id)
            if existing is None:
                raise SubCategoryNotFound(subcategory_id)

            if existing.name == FALLBACK_SUBCATEGORY_NAME:
                raise SubCategoryInUse(
                    subcategory_id,
                    "it is the rule engine's fallback subcategory",
                )

            merchants = await self._uow.merchants.find_by_subcategory_id(subcategory_id)
            if merchants:
                raise SubCategoryInUse(
                    subcategory_id,
                    f"{len(merchants)} merchant mappings reference it",
                )

            rules = await self._uow.rules.find_by_subcategory_id(subcategory_id)
            if rules:
                raise SubCategoryInUse(
                    subcategory_id,
                    f"{len(rules)} categorization rules reference it",
                )

            await self._uow.subcategories.delete(subcategory_id)

            await self._uow.outbox.add(
                event=SubCategoryDeletedEvent(
                    subcategory_id=existing.id,
                    name=existing.name,
                    category_id=existing.category_id,
                    is_default=existing.is_default,
                ),
                aggregate_type="subcategory",
                aggregate_id=str(existing.id),
            )
            await self._uow.commit()

    # ── Mapping ──

    @staticmethod
    def _to_dto(category: object) -> CategoryResponseDTO:
        cat_type = category.type.value if hasattr(category.type, "value") else str(category.type)
        return CategoryResponseDTO(
            id=category.id,
            name=category.name,
            type=cat_type,
            display_order=getattr(category, "display_order", 0),
        )

    @staticmethod
    def _to_sub_dto(sub: SubCategory) -> SubCategoryResponseDTO:
        return SubCategoryResponseDTO(
            id=sub.id,
            name=sub.name,
            category_id=sub.category_id,
            is_default=sub.is_default,
        )
