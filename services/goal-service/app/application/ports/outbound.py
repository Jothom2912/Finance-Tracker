"""
Outbound ports (driven adapters) - interfaces for infrastructure.
These define what the Goal application needs from the outside world.
"""

from abc import ABC, abstractmethod
from typing import Optional

from app.domain.entities import Goal


class IGoalRepository(ABC):
    """Port for goal persistence."""

    @abstractmethod
    async def get_by_id(self, goal_id: int) -> Optional[Goal]:
        pass

    @abstractmethod
    async def get_all(self, account_id: Optional[int] = None) -> list[Goal]:
        pass

    @abstractmethod
    async def create(self, goal: Goal) -> Goal:
        pass

    @abstractmethod
    async def update(self, goal: Goal) -> Goal:
        pass

    @abstractmethod
    async def delete(self, goal_id: int) -> bool:
        pass


class IAccountPort(ABC):
    """Anti-corruption port for account domain."""

    @abstractmethod
    async def exists(self, user_id: int) -> bool:
        pass
