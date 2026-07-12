"""Port interface for structured analytics data retrieval.

All methods return (result, elapsed_ms) — the pipeline aggregates per-step
latencies into StreamMetadata, so timing is part of the port contract.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import (
    BudgetStatusPayload,
    CategoryBreakdownItem,
    TransactionItem,
)


@runtime_checkable
class IAnalyticsPort(Protocol):
    async def get_largest_expenses(
        self,
        period: str,
        *,
        category: str | None = None,
        limit: int = 5,
    ) -> tuple[list[TransactionItem], float]: ...

    async def get_category_breakdown(
        self,
        period: str,
    ) -> tuple[list[CategoryBreakdownItem], float]: ...

    async def get_budget_status(
        self,
        period: str,
    ) -> tuple[BudgetStatusPayload, float]: ...
