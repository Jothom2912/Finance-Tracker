from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.outbound import ICategoryRepository
from app.domain.entities import Category, CategoryType
from app.domain.exceptions import CategoryNotFoundException
from app.models import CategoryModel, TransactionModel


class PostgresCategoryRepository(ICategoryRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, name: str, category_type: CategoryType) -> Category:
        model = CategoryModel(name=name, type=category_type.value)
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)

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

    async def update(self, category_id: int, **fields: object) -> Category:
        stmt = select(CategoryModel).where(CategoryModel.id == category_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            raise CategoryNotFoundException(category_id)

        for key, value in fields.items():
            if key == "type" and value is not None:
                value = value.value if isinstance(value, CategoryType) else value
            setattr(model, key, value)

        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def delete(self, category_id: int) -> bool:
        stmt = select(CategoryModel).where(CategoryModel.id == category_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            return False
        await self._session.delete(model)
        await self._session.flush()
        return True

    async def count_transactions(self, category_id: int) -> int:
        stmt = select(func.count()).select_from(TransactionModel).where(TransactionModel.category_id == category_id)
        result = await self._session.execute(stmt)
        return result.scalar_one()

    @staticmethod
    def _to_entity(model: CategoryModel) -> Category:
        return Category(
            id=model.id,
            name=model.name,
            type=CategoryType(model.type),
        )
