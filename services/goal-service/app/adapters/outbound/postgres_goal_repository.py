"""PostgreSQL implementation of Goal repository port."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.outbound import IGoalRepository
from app.domain.entities import Goal
from app.models import GoalModel


class AsyncPostgresGoalRepository(IGoalRepository):
    """Async PostgreSQL implementation of goal repository."""

    def __init__(self, db: AsyncSession):
        self._db = db

    async def get_by_id(self, goal_id: int) -> Optional[Goal]:
        result = await self._db.execute(select(GoalModel).where(GoalModel.idGoal == goal_id))
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_all(self, account_id: Optional[int] = None) -> list[Goal]:
        query = select(GoalModel)
        if account_id is not None:
            query = query.where(GoalModel.Account_idAccount == account_id)

        result = await self._db.execute(query.order_by(GoalModel.idGoal.desc()))
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]

    async def create(self, goal: Goal) -> Goal:
        model = GoalModel(
            name=goal.name,
            target_amount=goal.target_amount,
            current_amount=goal.current_amount,
            target_date=goal.target_date,
            status=goal.status,
            Account_idAccount=goal.account_id,
        )
        self._db.add(model)
        await self._db.commit()
        await self._db.refresh(model)
        return self._to_entity(model)

    async def update(self, goal: Goal) -> Goal:
        result = await self._db.execute(select(GoalModel).where(GoalModel.idGoal == goal.id))
        model = result.scalar_one_or_none()
        if model is None:
            raise ValueError(f"Goal with id {goal.id} not found")

        model.name = goal.name
        model.target_amount = goal.target_amount
        model.current_amount = goal.current_amount
        model.target_date = goal.target_date
        model.status = goal.status

        await self._db.commit()
        await self._db.refresh(model)
        return self._to_entity(model)

    async def delete(self, goal_id: int) -> bool:
        result = await self._db.execute(select(GoalModel).where(GoalModel.idGoal == goal_id))
        model = result.scalar_one_or_none()
        if model is None:
            return False

        await self._db.delete(model)
        await self._db.commit()
        return True

    def _to_entity(self, model: GoalModel) -> Goal:
        return Goal(
            id=model.idGoal,
            name=model.name,
            target_amount=float(model.target_amount) if model.target_amount is not None else 0.0,
            current_amount=float(model.current_amount) if model.current_amount is not None else 0.0,
            target_date=model.target_date,
            status=model.status,
            account_id=model.Account_idAccount,
        )
