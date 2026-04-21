"""
Inbound ports (driving adapters) - interfaces for use cases.
These define what the Goal application can do.
"""

from abc import ABC, abstractmethod
from typing import Optional

from app.application.dto import (
    Goal as GoalSchema,
)
from app.application.dto import (
    GoalBase,
    GoalCreate,
)


class IGoalService(ABC):
    """Inbound port defining goal use cases."""

    @abstractmethod
    def get_goal(self, goal_id: int) -> Optional[GoalSchema]:
        pass

    @abstractmethod
    def list_goals(self, account_id: int) -> list[GoalSchema]:
        pass

    @abstractmethod
    def create_goal(self, data: GoalCreate) -> GoalSchema:
        pass

    @abstractmethod
    def update_goal(self, goal_id: int, data: GoalBase) -> Optional[GoalSchema]:
        pass

    @abstractmethod
    def delete_goal(self, goal_id: int) -> bool:
        pass
