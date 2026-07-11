from __future__ import annotations

from datetime import date

from app.adapters.inbound.graphql_api import _MemoizedAnalyticsReadRepository
from app.application.service import AnalyticsService


class CountingReadRepository:
    def __init__(self) -> None:
        self.calls = 0
        self.transactions = [
            {
                "id": 1,
                "amount": -200,
                "description": "Groceries",
                "date": "2026-06-02",
                "type": "expense",
                "category_id": 10,
                "category_name": "Food",
                "subcategory_id": None,
                "subcategory_name": None,
                "account_id": 1,
                "categorization_tier": "rule",
            },
        ]

    def get_transactions(self, account_id, start_date=None, end_date=None):
        self.calls += 1
        return self.transactions


class CountingCategoryRepository:
    def __init__(self) -> None:
        self.calls = 0

    def get_categories(self):
        self.calls += 1
        return [{"id": 10, "name": "Mad & drikke", "type": "expense", "display_order": 1}]

    def get_subcategories(self):
        return []


def test_memoized_repo_fetches_once_for_same_key() -> None:
    inner = CountingReadRepository()
    repo = _MemoizedAnalyticsReadRepository(inner, {})

    first = repo.get_transactions(1, date(2026, 6, 1), date(2026, 6, 30))
    second = repo.get_transactions(1, date(2026, 6, 1), date(2026, 6, 30))

    assert inner.calls == 1
    assert first is second


def test_memoized_repo_distinct_periods_fetch_separately() -> None:
    inner = CountingReadRepository()
    repo = _MemoizedAnalyticsReadRepository(inner, {})

    repo.get_transactions(1, date(2026, 6, 1), date(2026, 6, 30))
    repo.get_transactions(1, date(2026, 5, 1), date(2026, 5, 31))

    assert inner.calls == 2


def test_two_resolver_calls_one_upstream_fetch() -> None:
    """Two overview computations over the same period (e.g. two fields of
    one dashboard query) must hit upstream once for transactions and once
    for the taxonomy — with identical results."""
    inner = CountingReadRepository()
    category_repo = CountingCategoryRepository()
    service = AnalyticsService(
        read_repo=_MemoizedAnalyticsReadRepository(inner, {}),
        category_repo=category_repo,
    )

    first = service.get_financial_overview(
        account_id=1, start_date=date(2026, 6, 1), end_date=date(2026, 6, 30)
    )
    second = service.get_financial_overview(
        account_id=1, start_date=date(2026, 6, 1), end_date=date(2026, 6, 30)
    )

    assert inner.calls == 1
    assert category_repo.calls == 1
    assert first == second
    assert first.total_expenses == 200
    assert first.expenses_by_category[0].category_name == "Mad & drikke"
