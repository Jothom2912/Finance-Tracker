"""
Outbound ports (driven adapters) for Budget bounded context.
Defines interfaces for infrastructure dependencies.
"""
from abc import ABC, abstractmethod
from typing import Optional

from backend.budget.domain.entities import Budget


class IBudgetRepository(ABC):
    """Port for budget persistence."""

    @abstractmethod
    def get_by_id(self, budget_id: int) -> Optional[Budget]:
        pass

    @abstractmethod
    def get_all(self, account_id: int) -> list[Budget]:
        pass

    @abstractmethod
    def create(self, budget: Budget) -> Budget:
        pass

    @abstractmethod
    def update(self, budget: Budget) -> Budget:
        pass

    @abstractmethod
    def delete(self, budget_id: int) -> bool:
        pass


class ICategoryPort(ABC):
    """Anti-corruption port for category domain lookups."""

    @abstractmethod
    def exists(self, category_id: int) -> bool:
        """Check if a category exists."""
        pass
