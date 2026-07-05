from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.outbound import ICategoryRepository
from app.domain.entities import Category, CategoryType
from app.models import CategoryModel


class PostgresCategoryRepository(ICategoryRepository):
    """Read-only repository over the event-synced categories read copy.

    Writes live in categorization-service (ADR-003); the taxonomy sync
    consumer maintains this table directly on the model.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_all(self) -> list[Category]:
        stmt = select(CategoryModel).order_by(CategoryModel.name)
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def find_by_id(self, category_id: int) -> Category | None:
        stmt = select(CategoryModel).where(CategoryModel.id == category_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def find_by_name(self, name: str) -> Category | None:
        stmt = select(CategoryModel).where(CategoryModel.name == name)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    @staticmethod
    def _to_entity(model: CategoryModel) -> Category:
        return Category(
            id=model.id,
            name=model.name,
            type=CategoryType(model.type),
        )
