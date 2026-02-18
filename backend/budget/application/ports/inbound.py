"""
Inbound ports (driving adapters) for Budget bounded context.
Defines the service interface for external consumers.
"""
from abc import ABC, abstractmethod
from typing import Optional

from backend.budget.application.dto import (
    BudgetCreateDTO,
    BudgetResponseDTO,
    BudgetUpdateDTO,
)


class IBudgetService(ABC):
    """Inbound port defining budget use cases."""

    @abstractmethod
    def get_budget(self, budget_id: int) -> Optional[BudgetResponseDTO]:
        pass

    @abstractmethod
    def list_budgets(self, account_id: int) -> list[BudgetResponseDTO]:
        pass

    @abstractmethod
    def create_budget(self, dto: BudgetCreateDTO) -> BudgetResponseDTO:
        pass

    @abstractmethod
    def update_budget(
        self, budget_id: int, dto: BudgetUpdateDTO
    ) -> Optional[BudgetResponseDTO]:
        pass

    @abstractmethod
    def delete_budget(self, budget_id: int) -> bool:
        pass
