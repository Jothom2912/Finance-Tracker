"""
Outbound ports (driven adapters) - interfaces for infrastructure.
These define what the Goal application needs from the outside world.
"""
from abc import ABC, abstractmethod
from typing import Optional

from backend.goal.domain.entities import Goal


class IGoalRepository(ABC):
    """Port for goal persistence."""

    @abstractmethod
    def get_by_id(self, goal_id: int) -> Optional[Goal]:
        pass

    @abstractmethod
    def get_all(self, account_id: Optional[int] = None) -> list[Goal]:
        pass

    @abstractmethod
    def create(self, goal: Goal) -> Goal:
        pass

    @abstractmethod
    def update(self, goal: Goal) -> Goal:
        pass

    @abstractmethod
    def delete(self, goal_id: int) -> bool:
        pass


class IAccountPort(ABC):
    """Anti-corruption port for account domain."""

    @abstractmethod
    def exists(self, account_id: int) -> bool:
        pass
