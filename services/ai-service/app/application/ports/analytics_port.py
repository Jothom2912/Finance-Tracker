"""Port interface for analytics data retrieval."""

from __future__ import annotations

from typing import Protocol

from app.domain.models import (
    BudgetStatusPayload,
    CategoryBreakdownItem,
    TransactionItem,
)


class IAnalyticsPort(Protocol):
    async def get_largest_expenses(
        self,
        period: str,
        *,
        category: str | None = None,
        limit: int = 5,
    ) -> list[TransactionItem]: ...

    async def get_category_breakdown(
        self,
        period: str,
    ) -> list[CategoryBreakdownItem]: ...

    async def get_budget_status(
        self,
        period: str,
    ) -> BudgetStatusPayload: ...
