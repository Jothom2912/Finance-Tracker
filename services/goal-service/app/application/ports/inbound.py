from __future__ import annotations

from abc import ABC, abstractmethod

from app.application.dto import Goal, GoalBase, GoalCreate


class IGoalService(ABC):
    @abstractmethod
    async def get_goal(self, goal_id: int) -> Goal | None: ...

    @abstractmethod
    async def list_goals(self, account_id: int) -> list[Goal]: ...

    @abstractmethod
    async def create_goal(self, data: GoalCreate) -> Goal: ...

    @abstractmethod
    async def update_goal(self, goal_id: int, data: GoalBase) -> Goal | None: ...

    @abstractmethod
    async def delete_goal(self, goal_id: int) -> bool: ...
