from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.outbound import ISubCategoryReadRepository
from app.domain.entities import SubCategory
from app.models import SubCategoryModel


class PostgresSubCategoryReadRepository(ISubCategoryReadRepository):
    """Read-only repository over the event-synced subcategories read copy.

    Writes live in categorization-service (ADR-003); the taxonomy sync
    consumer maintains this table directly on the model.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_id(self, subcategory_id: int) -> SubCategory | None:
        stmt = select(SubCategoryModel).where(SubCategoryModel.id == subcategory_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def find_by_ids(self, subcategory_ids: list[int]) -> dict[int, SubCategory]:
        if not subcategory_ids:
            return {}
        stmt = select(SubCategoryModel).where(SubCategoryModel.id.in_(subcategory_ids))
        result = await self._session.execute(stmt)
        return {m.id: self._to_entity(m) for m in result.scalars().all()}

    @staticmethod
    def _to_entity(model: SubCategoryModel) -> SubCategory:
        return SubCategory(
            id=model.id,
            name=model.name,
            category_id=model.category_id,
            is_default=model.is_default,
        )
