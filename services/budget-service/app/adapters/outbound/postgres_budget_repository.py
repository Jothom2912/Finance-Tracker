from __future__ import annotations

from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.outbound import IBudgetRepository
from app.domain.entities import Budget
from app.models import BudgetModel


class PostgresBudgetRepository(IBudgetRepository):

    def __init__(self, db: AsyncSession):
        self._db = db

    async def get_by_id(self, budget_id: int) -> Optional[Budget]:
        result = await self._db.execute(select(BudgetModel).where(BudgetModel.id == budget_id))
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_all(self, account_id: int) -> list[Budget]:
        result = await self._db.execute(select(BudgetModel).where(BudgetModel.account_id == account_id))
        return [self._to_entity(m) for m in result.scalars().all()]

    async def create(self, budget: Budget) -> Budget:
        model = BudgetModel(
            amount=budget.amount,
            budget_date=budget.budget_date,
            account_id=budget.account_id,
            category_id=budget.category_id,
        )
        self._db.add(model)
        await self._db.commit()
        await self._db.refresh(model)
        return self._to_entity(model)

    async def update(self, budget: Budget) -> Budget:
        result = await self._db.execute(select(BudgetModel).where(BudgetModel.id == budget.id))
        model = result.scalar_one_or_none()
        if not model:
            raise ValueError(f"Budget {budget.id} not found")
        model.amount = budget.amount
        model.budget_date = budget.budget_date
        model.category_id = budget.category_id
        await self._db.commit()
        await self._db.refresh(model)
        return self._to_entity(model)

    async def delete(self, budget_id: int) -> bool:
        result = await self._db.execute(delete(BudgetModel).where(BudgetModel.id == budget_id))
        await self._db.commit()
        return result.rowcount > 0

    @staticmethod
    def _to_entity(model: BudgetModel) -> Budget:
        return Budget(
            id=model.id,
            amount=float(model.amount),
            budget_date=model.budget_date,
            account_id=model.account_id,
            category_id=model.category_id,
        )
