from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.outbound import IMonthlyBudgetRepository
from app.domain.entities import BudgetLine, MonthlyBudget
from app.models import BudgetLineModel, MonthlyBudgetModel


class PostgresMonthlyBudgetRepository(IMonthlyBudgetRepository):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id_for_account(
        self, budget_id: int, account_id: int,
    ) -> Optional[MonthlyBudget]:
        result = await self._session.execute(
            select(MonthlyBudgetModel).where(
                MonthlyBudgetModel.id == budget_id,
                MonthlyBudgetModel.account_id == account_id,
            ),
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_account_and_period(
        self, account_id: int, month: int, year: int,
    ) -> Optional[MonthlyBudget]:
        result = await self._session.execute(
            select(MonthlyBudgetModel).where(
                MonthlyBudgetModel.account_id == account_id,
                MonthlyBudgetModel.month == month,
                MonthlyBudgetModel.year == year,
            ),
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def create(self, budget: MonthlyBudget) -> MonthlyBudget:
        model = MonthlyBudgetModel(
            month=budget.month,
            year=budget.year,
            account_id=budget.account_id,
            user_id=budget.user_id,
            lines=[
                BudgetLineModel(category_id=line.category_id, amount=line.amount)
                for line in budget.lines
            ],
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def update(self, budget: MonthlyBudget) -> MonthlyBudget:
        result = await self._session.execute(
            select(MonthlyBudgetModel).where(MonthlyBudgetModel.id == budget.id),
        )
        model = result.scalar_one_or_none()
        if not model:
            raise ValueError(f"MonthlyBudget {budget.id} not found")

        await self._session.execute(
            delete(BudgetLineModel).where(
                BudgetLineModel.monthly_budget_id == budget.id,
            ),
        )

        model.lines = [
            BudgetLineModel(
                monthly_budget_id=budget.id,
                category_id=line.category_id,
                amount=line.amount,
            )
            for line in budget.lines
        ]

        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def delete(self, budget_id: int, account_id: int) -> bool:
        result = await self._session.execute(
            delete(MonthlyBudgetModel).where(
                MonthlyBudgetModel.id == budget_id,
                MonthlyBudgetModel.account_id == account_id,
            ),
        )
        await self._session.flush()
        return result.rowcount > 0

    async def mark_closed(self, budget_id: int) -> bool:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        result = await self._session.execute(
            update(MonthlyBudgetModel)
            .where(
                MonthlyBudgetModel.id == budget_id,
                MonthlyBudgetModel.closed_at.is_(None),
            )
            .values(closed_at=now),
        )
        await self._session.flush()
        return result.rowcount > 0

    @staticmethod
    def _to_entity(model: MonthlyBudgetModel) -> MonthlyBudget:
        return MonthlyBudget(
            id=model.id,
            month=model.month,
            year=model.year,
            account_id=model.account_id,
            user_id=model.user_id,
            lines=[
                BudgetLine(
                    id=line.id,
                    category_id=line.category_id,
                    amount=float(line.amount),
                )
                for line in model.lines
            ],
            created_at=model.created_at,
            closed_at=model.closed_at,
        )
