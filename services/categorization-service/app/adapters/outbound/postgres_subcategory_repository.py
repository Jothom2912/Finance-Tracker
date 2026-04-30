from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.outbound import ISubCategoryRepository
from app.domain.entities import SubCategory
from app.models import SubCategoryModel


class PostgresSubCategoryRepository(ISubCategoryRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        name: str,
        category_id: int,
        is_default: bool = True,
    ) -> SubCategory:
        model = SubCategoryModel(name=name, category_id=category_id, is_default=is_default)
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def find_all(self) -> list[SubCategory]:
        stmt = select(SubCategoryModel).order_by(SubCategoryModel.name)
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def find_by_id(self, subcategory_id: int) -> Optional[SubCategory]:
        stmt = select(SubCategoryModel).where(SubCategoryModel.id == subcategory_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def find_by_name(self, name: str) -> Optional[SubCategory]:
        stmt = select(SubCategoryModel).where(SubCategoryModel.name == name)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def find_by_category_id(self, category_id: int) -> list[SubCategory]:
        stmt = (
            select(SubCategoryModel)
            .where(
                SubCategoryModel.category_id == category_id,
            )
            .order_by(SubCategoryModel.name)
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def delete(self, subcategory_id: int) -> bool:
        stmt = select(SubCategoryModel).where(SubCategoryModel.id == subcategory_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            return False
        await self._session.delete(model)
        await self._session.flush()
        return True

    @staticmethod
    def _to_entity(model: SubCategoryModel) -> SubCategory:
        return SubCategory(
            id=model.id,
            name=model.name,
            category_id=model.category_id,
            is_default=model.is_default,
        )
