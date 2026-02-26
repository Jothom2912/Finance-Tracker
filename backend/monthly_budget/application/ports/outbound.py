"""
Outbound ports (driven adapters) for MonthlyBudget bounded context.
"""
from abc import ABC, abstractmethod
from typing import Optional

from backend.monthly_budget.domain.entities import MonthlyBudget


class IMonthlyBudgetRepository(ABC):
    """Port for monthly budget persistence."""

    @abstractmethod
    def get_by_id(self, budget_id: int) -> Optional[MonthlyBudget]:
        pass

    @abstractmethod
    def get_by_account_and_period(
        self, account_id: int, month: int, year: int
    ) -> Optional[MonthlyBudget]:
        pass

    @abstractmethod
    def create(self, budget: MonthlyBudget) -> MonthlyBudget:
        pass

    @abstractmethod
    def update(self, budget: MonthlyBudget) -> MonthlyBudget:
        pass

    @abstractmethod
    def delete(self, budget_id: int) -> bool:
        pass


class ITransactionPort(ABC):
    """Anti-corruption port for reading expense data from transactions."""

    @abstractmethod
    def get_expenses_by_category(
        self, account_id: int, month: int, year: int
    ) -> dict[int, float]:
        """Return {category_id: total_spent} for the given period."""
        pass


class ICategoryPort(ABC):
    """Anti-corruption port for category lookups."""

    @abstractmethod
    def exists(self, category_id: int) -> bool:
        pass

    @abstractmethod
    def get_name(self, category_id: int) -> Optional[str]:
        pass

    @abstractmethod
    def get_all_names(self) -> dict[int, str]:
        """Return {category_id: name} for all categories."""
        pass
