"""Unit tests for intent dispatcher.

Verifies that each IntentName routes to the correct adapter method with
correct parameters, and that unknown intents raise ValueError.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from app.application.intent_dispatcher import dispatch
from app.domain.models import (
    BudgetStatusItem,
    BudgetStatusPayload,
    CategoryBreakdownItem,
    CategoryBreakdownPayload,
    DataKind,
    IntentName,
    ResolvedIntent,
    TransactionItem,
    TransactionListPayload,
)


def _make_items(n: int = 3) -> list[TransactionItem]:
    return [
        TransactionItem(
            id=i, date=f"2026-04-{i:02d}", amount=100.0 * i,
            category="Test", description=f"Item {i}",
        )
        for i in range(1, n + 1)
    ]


def _make_budget() -> BudgetStatusPayload:
    return BudgetStatusPayload(
        items=[
            BudgetStatusItem(
                category_name="Dagligvarer", budget_amount=3000,
                spent_amount=2500, remaining_amount=500, percentage_used=83.3,
            ),
        ],
        total_budget=3000, total_spent=2500, total_remaining=500,
        over_budget_count=0,
    )


@pytest.fixture()
def analytics() -> AsyncMock:
    mock = AsyncMock()
    mock.get_largest_expenses.return_value = (_make_items(), 42.0)
    mock.get_category_breakdown.return_value = (
        [CategoryBreakdownItem(category="Dagligvarer", amount=2500, percentage=60.0)],
        35.0,
    )
    mock.get_budget_status.return_value = (_make_budget(), 50.0)
    return mock


@pytest.fixture()
def search() -> MagicMock:
    mock = MagicMock()
    mock.search.return_value = (_make_items(2), 20.0)
    return mock


async def test_dispatch_largest_expense(analytics: AsyncMock, search: MagicMock) -> None:
    intent = ResolvedIntent(intent=IntentName.LARGEST_EXPENSE, period="2026-04")
    data, elapsed = await dispatch(intent, analytics, search)

    analytics.get_largest_expenses.assert_awaited_once_with("2026-04", category=None)
    assert data.kind == DataKind.TRANSACTION_LIST
    assert isinstance(data.payload, TransactionListPayload)
    assert data.payload.highlight_id == 1
    assert elapsed == 42.0


async def test_dispatch_largest_expense_with_category(
    analytics: AsyncMock, search: MagicMock,
) -> None:
    intent = ResolvedIntent(
        intent=IntentName.LARGEST_EXPENSE, period="2026-04",
        slots={"category": "dagligvarer"},
    )
    data, elapsed = await dispatch(intent, analytics, search)

    analytics.get_largest_expenses.assert_awaited_once_with(
        "2026-04", category="dagligvarer",
    )


async def test_dispatch_category_breakdown(
    analytics: AsyncMock, search: MagicMock,
) -> None:
    intent = ResolvedIntent(intent=IntentName.CATEGORY_BREAKDOWN, period="2026-04")
    data, elapsed = await dispatch(intent, analytics, search)

    analytics.get_category_breakdown.assert_awaited_once_with("2026-04")
    assert data.kind == DataKind.CATEGORY_BREAKDOWN
    assert isinstance(data.payload, CategoryBreakdownPayload)
    assert elapsed == 35.0


async def test_dispatch_transaction_search(
    analytics: AsyncMock, search: MagicMock,
) -> None:
    intent = ResolvedIntent(
        intent=IntentName.TRANSACTION_SEARCH, period="2026-04",
        slots={"query": "kaffe"},
    )
    data, elapsed = await dispatch(intent, analytics, search)

    assert data.kind == DataKind.TRANSACTION_LIST
    assert isinstance(data.payload, TransactionListPayload)


async def test_dispatch_budget_status(
    analytics: AsyncMock, search: MagicMock,
) -> None:
    intent = ResolvedIntent(intent=IntentName.BUDGET_STATUS, period="2026-03")
    data, elapsed = await dispatch(intent, analytics, search)

    analytics.get_budget_status.assert_awaited_once_with("2026-03")
    assert data.kind == DataKind.BUDGET_STATUS
    assert isinstance(data.payload, BudgetStatusPayload)
    assert elapsed == 50.0


async def test_dispatch_unknown_intent_raises(
    analytics: AsyncMock, search: MagicMock,
) -> None:
    intent = MagicMock(spec=ResolvedIntent)
    intent.intent = "future_unsupported_intent"
    intent.period = "2026-04"
    intent.slots = {}

    with pytest.raises(ValueError, match="Unknown intent"):
        await dispatch(intent, analytics, search)
