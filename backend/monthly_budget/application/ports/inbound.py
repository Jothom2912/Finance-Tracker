"""
Inbound ports (driving adapters) for MonthlyBudget bounded context.
"""
from abc import ABC, abstractmethod
from typing import Optional

from backend.monthly_budget.application.dto import (
    MonthlyBudgetCreate,
    MonthlyBudgetResponse,
    MonthlyBudgetSummary,
    MonthlyBudgetUpdate,
    CopyBudgetRequest,
)


class IMonthlyBudgetService(ABC):
    """Inbound port defining monthly budget use cases."""

    @abstractmethod
    def get_or_none(
        self, account_id: int, month: int, year: int
    ) -> Optional[MonthlyBudgetResponse]:
        pass

    @abstractmethod
    def create(
        self, account_id: int, dto: MonthlyBudgetCreate
    ) -> MonthlyBudgetResponse:
        pass

    @abstractmethod
    def update(
        self, budget_id: int, dto: MonthlyBudgetUpdate
    ) -> MonthlyBudgetResponse:
        pass

    @abstractmethod
    def delete(self, budget_id: int) -> bool:
        pass

    @abstractmethod
    def copy_to_month(
        self, account_id: int, dto: CopyBudgetRequest
    ) -> MonthlyBudgetResponse:
        pass

    @abstractmethod
    def get_summary(
        self, account_id: int, month: int, year: int
    ) -> MonthlyBudgetSummary:
        pass
