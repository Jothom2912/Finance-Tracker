from __future__ import annotations

from contracts.events.goal import GoalCreatedEvent, GoalDeletedEvent, GoalUpdatedEvent

from app.application.dto import Goal as GoalDTO
from app.application.dto import GoalBase, GoalCreate
from app.application.ports.inbound import IGoalService
from app.application.ports.outbound import IAccountPort, IUnitOfWork
from app.domain.entities import Goal
from app.domain.exceptions import AccountNotFoundForGoal


class GoalService(IGoalService):
    def __init__(self, uow: IUnitOfWork, account_port: IAccountPort) -> None:
        self._uow = uow
        self._account_port = account_port

    async def get_goal(self, goal_id: int) -> GoalDTO | None:
        async with self._uow:
            goal = await self._uow.goals.get_by_id(goal_id)
        return self._to_dto(goal) if goal else None

    async def list_goals(self, account_id: int) -> list[GoalDTO]:
        async with self._uow:
            goals = await self._uow.goals.get_all(account_id=account_id)
        return [self._to_dto(goal) for goal in goals]

    async def create_goal(self, data: GoalCreate) -> GoalDTO:
        if not await self._account_port.exists(data.Account_idAccount):
            raise AccountNotFoundForGoal(data.Account_idAccount)

        goal = Goal(
            id=None,
            name=data.name,
            target_amount=data.target_amount,
            current_amount=data.current_amount,
            target_date=data.target_date,
            status=data.status or "active",
            account_id=data.Account_idAccount,
        )

        async with self._uow:
            created = await self._uow.goals.create(goal)
            await self._uow.outbox.add(
                event=GoalCreatedEvent(
                    goal_id=created.id or 0,
                    user_id=created.account_id,
                    name=created.name,
                    target_amount=str(created.target_amount),
                    current_amount=str(created.current_amount),
                    target_date=created.target_date,
                    status=created.status,
                ),
                aggregate_type="goal",
                aggregate_id=str(created.id or 0),
            )
            await self._uow.commit()
        return self._to_dto(created)

    async def update_goal(self, goal_id: int, data: GoalBase) -> GoalDTO | None:
        async with self._uow:
            existing = await self._uow.goals.get_by_id(goal_id)
            if not existing:
                return None
            updated = Goal(
                id=goal_id,
                name=data.name,
                target_amount=data.target_amount,
                current_amount=data.current_amount,
                target_date=data.target_date,
                status=data.status,
                account_id=existing.account_id,
            )
            result = await self._uow.goals.update(updated)
            await self._uow.outbox.add(
                event=GoalUpdatedEvent(
                    goal_id=result.id or 0,
                    user_id=result.account_id,
                    name=result.name,
                    target_amount=str(result.target_amount),
                    current_amount=str(result.current_amount),
                    target_date=result.target_date,
                    status=result.status,
                ),
                aggregate_type="goal",
                aggregate_id=str(result.id or 0),
            )
            await self._uow.commit()
        return self._to_dto(result)

    async def delete_goal(self, goal_id: int) -> bool:
        async with self._uow:
            existing = await self._uow.goals.get_by_id(goal_id)
            if not existing:
                return False
            deleted = await self._uow.goals.delete(goal_id)
            if not deleted:
                return False
            await self._uow.outbox.add(
                event=GoalDeletedEvent(goal_id=goal_id, user_id=existing.account_id),
                aggregate_type="goal",
                aggregate_id=str(goal_id),
            )
            await self._uow.commit()
        return True

    def _to_dto(self, goal: Goal) -> GoalDTO:
        return GoalDTO(
            idGoal=goal.id,
            name=goal.name,
            target_amount=goal.target_amount,
            current_amount=goal.current_amount,
            target_date=goal.target_date,
            status=goal.status,
            Account_idAccount=goal.account_id,
        )
