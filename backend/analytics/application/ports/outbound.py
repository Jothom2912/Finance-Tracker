"""
Outbound ports for Analytics bounded context.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Optional


class IAnalyticsReadRepository(ABC):
    """Read-focused port for analytics aggregations."""

    @abstractmethod
    def get_transactions(
        self,
        account_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 10000,
    ) -> list[dict]:
        pass

    @abstractmethod
    def get_categories(self) -> list[dict]:
        pass

    @abstractmethod
    def get_budgets(self, account_id: int) -> list[dict]:
        pass
