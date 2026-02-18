"""
Goal Service - Application layer use case implementation.
Orchestrates domain logic and infrastructure through ports.
"""
import logging
from typing import Optional

from backend.goal.application.ports.inbound import IGoalService
from backend.goal.application.ports.outbound import (
    IGoalRepository,
    IAccountPort,
)
from backend.goal.domain.entities import Goal
from backend.goal.domain.exceptions import AccountNotFoundForGoal
from backend.shared.schemas.goal import (
    GoalCreate,
    GoalBase,
    Goal as GoalSchema,
)

logger = logging.getLogger(__name__)


class GoalService(IGoalService):
    """
    Application service implementing goal use cases.

    Uses constructor injection for all dependencies.
    """

    def __init__(
        self,
        goal_repository: IGoalRepository,
        account_port: IAccountPort,
    ):
        self._goal_repo = goal_repository
        self._account_port = account_port

    # ------------------------------------------------------------------
    # Query use cases
    # ------------------------------------------------------------------

    def get_goal(self, goal_id: int) -> Optional[GoalSchema]:
        """Get a single goal by ID."""
        goal = self._goal_repo.get_by_id(goal_id)
        if not goal:
            return None
        return self._to_dto(goal)

    def list_goals(self, account_id: int) -> list[GoalSchema]:
        """List all goals for a given account."""
        goals = self._goal_repo.get_all(account_id=account_id)
        return [self._to_dto(g) for g in goals]

    # ------------------------------------------------------------------
    # Command use cases
    # ------------------------------------------------------------------

    def create_goal(self, data: GoalCreate) -> GoalSchema:
        """Create a new goal. Validates that account exists."""
        if not self._account_port.exists(data.Account_idAccount):
            raise AccountNotFoundForGoal(data.Account_idAccount)

        goal = Goal(
            id=None,
            name=data.name,
            target_amount=data.target_amount,
            current_amount=data.current_amount or 0.0,
            target_date=data.target_date,
            status=data.status or "active",
            account_id=data.Account_idAccount,
        )

        created = self._goal_repo.create(goal)
        return self._to_dto(created)

    def update_goal(
        self, goal_id: int, data: GoalBase
    ) -> Optional[GoalSchema]:
        """Update an existing goal."""
        existing = self._goal_repo.get_by_id(goal_id)
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

        result = self._goal_repo.update(updated_goal)
        return self._to_dto(result)

    def delete_goal(self, goal_id: int) -> bool:
        """Delete a goal."""
        return self._goal_repo.delete(goal_id)

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
