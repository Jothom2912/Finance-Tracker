from __future__ import annotations

from datetime import date

import pytest
from app.application.service import AnalyticsService


class FakeAnalyticsReadRepository:
    def __init__(self) -> None:
        self.transactions = [
            {
                "idTransaction": 1,
                "amount": 1000,
                "description": "Salary",
                "date": "2026-06-01",
                "type": "income",
                "Category_idCategory": None,
                "Account_idAccount": 1,
                "categorization_tier": None,
            },
            {
                "idTransaction": 2,
                "amount": -200,
                "description": "Groceries",
                "date": "2026-06-02",
                "type": "expense",
                "Category_idCategory": 10,
                "Account_idAccount": 1,
                "categorization_tier": "rule",
            },
            {
                "idTransaction": 3,
                "amount": -50,
                "description": "Bus",
                "date": "2026-06-03",
                "type": "expense",
                "Category_idCategory": None,
                "Account_idAccount": 1,
                "categorization_tier": None,
            },
        ]

    def get_transactions(self, **_kwargs):
        return self.transactions

    def get_categories(self):
        return [{"idCategory": 10, "name": "Food"}]


def test_financial_overview_calculates_income_expenses_and_categories() -> None:
    service = AnalyticsService(FakeAnalyticsReadRepository())

    overview = service.get_financial_overview(
        account_id=1,
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 30),
    )

    assert overview.total_income == 1000
    assert overview.total_expenses == 250
    assert overview.net_change_in_period == 750
    assert overview.current_account_balance == 750
    assert overview.expenses_by_category == {"Food": 200, "Ukategoriseret": 50}


def test_financial_overview_rejects_invalid_date_range() -> None:
    service = AnalyticsService(FakeAnalyticsReadRepository())

    with pytest.raises(ValueError, match="Startdato"):
        service.get_financial_overview(
            account_id=1,
            start_date=date(2026, 7, 1),
            end_date=date(2026, 6, 1),
        )


def test_list_transaction_projections_filters_by_category_and_type() -> None:
    service = AnalyticsService(FakeAnalyticsReadRepository())

    projections = service.list_transaction_projections(
        account_id=1,
        category_id=10,
        tx_type="expense",
    )

    assert len(projections) == 1
    assert projections[0].description == "Groceries"
    assert projections[0].category_id == 10


def test_list_transaction_projections_requires_account_id() -> None:
    service = AnalyticsService(FakeAnalyticsReadRepository())

    with pytest.raises(ValueError, match="Account ID"):
        service.list_transaction_projections(account_id=0)
