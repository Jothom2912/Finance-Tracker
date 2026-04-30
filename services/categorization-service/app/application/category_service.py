"""CategoryService — CRUD for taxonomy (categories + subcategories).

This service owns the master category data and emits category.*
events via the transactional outbox for downstream consumers.
"""

from __future__ import annotations

import logging

from contracts.events.category import (
    CategoryCreatedEvent,
    CategoryDeletedEvent,
    CategoryUpdatedEvent,
)

from app.application.dto import (
    CategoryResponseDTO,
    CreateCategoryDTO,
    SubCategoryResponseDTO,
    UpdateCategoryDTO,
)
from app.application.ports.outbound import IUnitOfWork
from app.domain.exceptions import CategoryNotFound, DuplicateCategoryName
from app.domain.value_objects import CategoryType

logger = logging.getLogger(__name__)


class CategoryService:
    def __init__(self, uow: IUnitOfWork) -> None:
        self._uow = uow

    async def create_category(self, dto: CreateCategoryDTO) -> CategoryResponseDTO:
        async with self._uow:
            existing = await self._uow.categories.find_by_name(dto.name)
            if existing is not None:
                raise DuplicateCategoryName(dto.name)

            category = await self._uow.categories.create(
                dto.name,
                CategoryType(dto.type),
            )

            await self._uow.outbox.add(
                event=CategoryCreatedEvent(
                    category_id=category.id,
                    name=category.name,
                    category_type=category.type.value,
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
                fields["type"] = dto.type

            if not fields:
                return self._to_dto(existing)

            previous_name = existing.name
            previous_type = existing.type.value if hasattr(existing.type, "value") else str(existing.type)

            updated = await self._uow.categories.update(category_id, **fields)

            await self._uow.outbox.add(
                event=CategoryUpdatedEvent(
                    category_id=updated.id,
                    name=updated.name,
                    category_type=updated.type.value if hasattr(updated.type, "value") else str(updated.type),
                    previous_name=previous_name,
                    previous_type=previous_type,
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

            await self._uow.categories.delete(category_id)

            await self._uow.outbox.add(
                event=CategoryDeletedEvent(
                    category_id=existing.id,
                    name=existing.name,
                    category_type=existing.type.value if hasattr(existing.type, "value") else str(existing.type),
                ),
                aggregate_type="category",
                aggregate_id=str(existing.id),
            )
            await self._uow.commit()

    async def list_subcategories(self, category_id: int) -> list[SubCategoryResponseDTO]:
        async with self._uow:
            category = await self._uow.categories.find_by_id(category_id)
            if category is None:
                raise CategoryNotFound(category_id)
            subs = await self._uow.subcategories.find_by_category_id(category_id)
            return [
                SubCategoryResponseDTO(
                    id=s.id,
                    name=s.name,
                    category_id=s.category_id,
                    is_default=s.is_default,
                )
                for s in subs
            ]

    @staticmethod
    def _to_dto(category: object) -> CategoryResponseDTO:
        cat_type = category.type.value if hasattr(category.type, "value") else str(category.type)
        return CategoryResponseDTO(
            id=category.id,
            name=category.name,
            type=cat_type,
            display_order=getattr(category, "display_order", 0),
        )
