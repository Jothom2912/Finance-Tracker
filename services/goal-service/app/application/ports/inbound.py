from __future__ import annotations

from abc import ABC, abstractmethod

from app.application.dto import (
    AllocationHistoryEntryResponse,
    Goal,
    GoalBase,
    GoalCreate,
    UnallocatedSurplusResponse,
)


class IGoalService(ABC):
    @abstractmethod
    async def get_goal(self, goal_id: int, user_id: int) -> Goal | None: ...

    @abstractmethod
    async def list_goals(self, account_id: int, user_id: int) -> list[Goal]: ...

    @abstractmethod
    async def create_goal(self, data: GoalCreate, user_id: int) -> Goal: ...

    @abstractmethod
    async def update_goal(self, goal_id: int, data: GoalBase, user_id: int) -> Goal | None: ...

    @abstractmethod
    async def delete_goal(self, goal_id: int, user_id: int) -> bool: ...

    @abstractmethod
    async def set_default_goal(self, goal_id: int, user_id: int) -> Goal | None: ...

    @abstractmethod
    async def clear_default_goal(self, goal_id: int, user_id: int) -> Goal | None: ...

    @abstractmethod
    async def get_allocation_history(
        self, goal_id: int, user_id: int
    ) -> list[AllocationHistoryEntryResponse] | None: ...

    @abstractmethod
    async def get_unallocated_surplus(self, account_id: int, user_id: int) -> UnallocatedSurplusResponse: ...
