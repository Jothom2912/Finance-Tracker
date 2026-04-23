"""
Goal Service - Application layer use case implementation.
Orchestrates domain logic and infrastructure through ports.
"""

import logging
from typing import Optional

from contracts.events.goal import GoalCreatedEvent, GoalDeletedEvent, GoalUpdatedEvent

from app.application.dto import (
    Goal as GoalSchema,
)
from app.application.dto import (
    GoalBase,
    GoalCreate,
)
from app.application.ports.inbound import IGoalService
from app.application.ports.outbound import (
    IAccountPort,
    IUnitOfWork,
)
from app.domain.entities import Goal
from app.domain.exceptions import AccountNotFoundForGoal

logger = logging.getLogger(__name__)


class GoalService(IGoalService):
    """
    Application service implementing goal use cases.

    Uses constructor injection for all dependencies.
    """

    def __init__(
        self,
        uow: IUnitOfWork,
        account_port: IAccountPort,
    ):
        self._uow = uow
        self._account_port = account_port

    # ------------------------------------------------------------------
    # Query use cases
    # ------------------------------------------------------------------

    async def get_goal(self, goal_id: int) -> Optional[GoalSchema]:
        """Get a single goal by ID."""
        async with self._uow:
            goal = await self._uow.goals.get_by_id(goal_id)
        if not goal:
            return None
        return self._to_dto(goal)

    async def list_goals(self, account_id: int) -> list[GoalSchema]:
        """List all goals for a given account."""
        async with self._uow:
            goals = await self._uow.goals.get_all(account_id=account_id)
        return [self._to_dto(g) for g in goals]

    # ------------------------------------------------------------------
    # Command use cases
    # ------------------------------------------------------------------

    async def create_goal(self, data: GoalCreate) -> GoalSchema:
        """Create a new goal. Validates that account exists."""
        user_id = data.Account_idAccount
        if not await self._account_port.exists(user_id):
            raise AccountNotFoundForGoal(user_id)

        goal = Goal(
            id=None,
            name=data.name,
            target_amount=data.target_amount,
            current_amount=data.current_amount or 0.0,
            target_date=data.target_date,
            status=data.status or "active",
            account_id=user_id,
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

    async def update_goal(self, goal_id: int, data: GoalBase) -> Optional[GoalSchema]:
        """Update an existing goal."""
        async with self._uow:
            existing = await self._uow.goals.get_by_id(goal_id)
            if not existing:
                return None

            updated_goal = Goal(
                id=goal_id,
                name=data.name,
                target_amount=data.target_amount,
                current_amount=data.current_amount,
                target_date=data.target_date,
                status=data.status,
                account_id=existing.account_id,
            )

            result = await self._uow.goals.update(updated_goal)
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
        """Delete a goal."""
        async with self._uow:
            existing = await self._uow.goals.get_by_id(goal_id)
            if not existing:
                return False

            deleted = await self._uow.goals.delete(goal_id)
            if not deleted:
                return False

            await self._uow.outbox.add(
                event=GoalDeletedEvent(
                    goal_id=goal_id,
                    user_id=existing.account_id,
                ),
                aggregate_type="goal",
                aggregate_id=str(goal_id),
            )
            await self._uow.commit()

        return True

    # ------------------------------------------------------------------
    # Mapping helpers
    # ------------------------------------------------------------------

    def _to_dto(self, goal: Goal) -> GoalSchema:
        return GoalSchema(
            idGoal=goal.id,
            name=goal.name,
            target_amount=goal.target_amount,
            current_amount=goal.current_amount,
            target_date=goal.target_date,
            status=goal.status,
            Account_idAccount=goal.account_id,
        )
