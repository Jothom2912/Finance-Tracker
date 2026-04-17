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
    UpdateCategoryDTO,
)
from app.application.ports.inbound import ICategoryService
from app.application.ports.outbound import IUnitOfWork
from app.domain.entities import Category
from app.domain.exceptions import (
    CategoryInUseException,
    CategoryNotFoundException,
    DuplicateCategoryNameException,
)

logger = logging.getLogger(__name__)


class CategoryService(ICategoryService):
    """Application service for category aggregate.

    Uses the same UoW as TransactionService so categories and outbox
    events are committed atomically.
    """

    def __init__(self, uow: IUnitOfWork) -> None:
        self._uow = uow

    async def create_category(self, dto: CreateCategoryDTO) -> CategoryResponseDTO:
        async with self._uow:
            existing = await self._uow.categories.find_by_name(dto.name)
            if existing is not None:
                raise DuplicateCategoryNameException(dto.name)

            category = await self._uow.categories.create(dto.name, dto.type)

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

        return self._to_response(category)

    async def get_categories(self) -> list[CategoryResponseDTO]:
        async with self._uow:
            categories = await self._uow.categories.find_all()
        return [self._to_response(c) for c in categories]

    async def get_category(self, category_id: int) -> CategoryResponseDTO:
        async with self._uow:
            category = await self._uow.categories.find_by_id(category_id)
        if category is None:
            raise CategoryNotFoundException(category_id)
        return self._to_response(category)

    async def update_category(
        self,
        category_id: int,
        dto: UpdateCategoryDTO,
    ) -> CategoryResponseDTO:
        fields = dto.model_dump(exclude_unset=True)

        async with self._uow:
            existing = await self._uow.categories.find_by_id(category_id)
            if existing is None:
                raise CategoryNotFoundException(category_id)

            if not fields:
                return self._to_response(existing)

            if "name" in fields and fields["name"] != existing.name:
                duplicate = await self._uow.categories.find_by_name(fields["name"])
                if duplicate is not None:
                    raise DuplicateCategoryNameException(fields["name"])

            previous_name = existing.name
            previous_type = existing.type.value

            updated = await self._uow.categories.update(category_id, **fields)

            await self._uow.outbox.add(
                event=CategoryUpdatedEvent(
                    category_id=updated.id,
                    name=updated.name,
                    category_type=updated.type.value,
                    previous_name=previous_name,
                    previous_type=previous_type,
                ),
                aggregate_type="category",
                aggregate_id=str(updated.id),
            )
            await self._uow.commit()

        return self._to_response(updated)

    async def delete_category(self, category_id: int) -> None:
        async with self._uow:
            existing = await self._uow.categories.find_by_id(category_id)
            if existing is None:
                raise CategoryNotFoundException(category_id)

            tx_count = await self._uow.categories.count_transactions(category_id)
            if tx_count > 0:
                raise CategoryInUseException(category_id)

            await self._uow.categories.delete(category_id)

            await self._uow.outbox.add(
                event=CategoryDeletedEvent(
                    category_id=existing.id,
                    name=existing.name,
                    category_type=existing.type.value,
                ),
                aggregate_type="category",
                aggregate_id=str(existing.id),
            )
            await self._uow.commit()

    @staticmethod
    def _to_response(entity: Category) -> CategoryResponseDTO:
        return CategoryResponseDTO(
            id=entity.id,
            name=entity.name,
            type=entity.type,
        )
