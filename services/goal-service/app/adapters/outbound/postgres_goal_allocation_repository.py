from __future__ import annotations

from decimal import Decimal
from typing import Literal
from uuid import uuid4

from app.application.ports.outbound import (
    IGoalAllocationRepository,
    IGoalSavingsRepository,
    IUnallocatedBudgetSurplusRepository,
)
from app.domain.entities import Goal
from app.models import GoalAllocationHistoryModel, GoalModel, UnallocatedBudgetSurplusModel
from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession


class PostgresGoalSavingsRepository(IGoalSavingsRepository):
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_default_savings_goal(self, account_id: int) -> Goal | None:
        result = await self._db.execute(
            select(GoalModel).where(
                GoalModel.Account_idAccount == account_id,
                GoalModel.is_default_savings_goal.is_(True),
            )
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def increment_current_amount(self, goal_id: int, amount: Decimal) -> None:
        result = await self._db.execute(select(GoalModel).where(GoalModel.idGoal == goal_id))
        model = result.scalar_one_or_none()
        if model is None:
            raise ValueError(f"Goal with id {goal_id} not found")

        model.current_amount = Decimal(str(model.current_amount)) + amount
        await self._db.flush()

    @staticmethod
    def _to_entity(model: GoalModel) -> Goal:
        return Goal(
            id=model.idGoal,
            name=model.name,
            target_amount=Decimal(str(model.target_amount)),
            current_amount=Decimal(str(model.current_amount)),
            target_date=model.target_date,
            status=model.status,
            account_id=model.Account_idAccount,
        )


class PostgresGoalAllocationRepository(IGoalAllocationRepository):
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def source_key_exists(self, source_key: str) -> bool:
        result = await self._db.execute(select(exists().where(GoalAllocationHistoryModel.source_key == source_key)))
        return bool(result.scalar())

    async def add_allocation(
        self,
        *,
        source_key: str,
        goal_id: int,
        account_id: int,
        amount: Decimal,
        correlation_id: str | None,
    ) -> None:
        self._db.add(
            GoalAllocationHistoryModel(
                id=str(uuid4()),
                source_key=source_key,
                goal_id=goal_id,
                account_id=account_id,
                amount=amount,
                correlation_id=correlation_id,
            )
        )
        await self._db.flush()


class PostgresUnallocatedBudgetSurplusRepository(IUnallocatedBudgetSurplusRepository):
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def source_key_exists(self, source_key: str) -> bool:
        result = await self._db.execute(select(exists().where(UnallocatedBudgetSurplusModel.source_key == source_key)))
        return bool(result.scalar())

    async def add_unallocated(
        self,
        *,
        source_key: str,
        account_id: int,
        amount: Decimal,
        reason: Literal["no_default_goal", "goal_already_complete"],
        correlation_id: str | None,
    ) -> None:
        self._db.add(
            UnallocatedBudgetSurplusModel(
                id=str(uuid4()),
                source_key=source_key,
                account_id=account_id,
                amount=amount,
                reason=reason,
                correlation_id=correlation_id,
            )
        )
        await self._db.flush()
