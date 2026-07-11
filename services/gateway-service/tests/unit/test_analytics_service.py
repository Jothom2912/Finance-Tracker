from __future__ import annotations

from datetime import date

import pytest
from app.application.service import AnalyticsService


class FakeAnalyticsReadRepository:
    """Rows use the normalized ADR-003 keys from transaction_client."""

    def __init__(self) -> None:
        self.transactions = [
            {
                "id": 1,
                "amount": 1000,
                "description": "Salary",
                "date": "2026-06-01",
                "type": "income",
                "category_id": None,
                "category_name": None,
                "subcategory_id": None,
                "subcategory_name": None,
                "account_id": 1,
                "categorization_tier": None,
            },
            {
                "id": 2,
                "amount": -200,
                "description": "Groceries",
                "date": "2026-06-02",
                "type": "expense",
                "category_id": 10,
                "category_name": "Food",
                "subcategory_id": 101,
                "subcategory_name": "Dagligvarer",
                "account_id": 1,
                "categorization_tier": "rule",
            },
            {
                "id": 3,
                "amount": -50,
                "description": "Bus",
                "date": "2026-06-03",
                "type": "expense",
                "category_id": None,
                "category_name": None,
                "subcategory_id": None,
                "subcategory_name": None,
                "account_id": 1,
                "categorization_tier": None,
            },
            {
                "id": 4,
                "amount": -100,
                "description": "Wolt",
                "date": "2026-06-04",
                "type": "expense",
                "category_id": 10,
                "category_name": "Food",
                "subcategory_id": 102,
                "subcategory_name": "Takeaway",
                "account_id": 1,
                "categorization_tier": "rule",
            },
            {
                "id": 5,
                "amount": -25,
                "description": "Manual food expense",
                "date": "2026-06-05",
                "type": "expense",
                "category_id": 10,
                "category_name": "Food",
                "subcategory_id": None,
                "subcategory_name": None,
                "account_id": 1,
                "categorization_tier": "manual",
            },
        ]

    def get_transactions(self, **_kwargs):
        return self.transactions


class FakeCategoryReadRepository:
    def __init__(self, categories: list[dict] | None = None) -> None:
        # Authoritative taxonomy names — deliberately different from the
        # denormalized row name to prove the taxonomy wins.
        self._categories = (
            categories
            if categories is not None
            else [
                {"id": 10, "name": "Mad & drikke", "type": "expense", "display_order": 1},
            ]
        )

    def get_categories(self):
        return self._categories

    def get_subcategories(self):
        return [
            {"id": 101, "name": "Dagligvarer", "category_id": 10, "is_default": True},
            {"id": 102, "name": "Takeaway", "category_id": 10, "is_default": True},
        ]


def _service(category_repo=None) -> AnalyticsService:
    return AnalyticsService(
        FakeAnalyticsReadRepository(),
        category_repo=category_repo if category_repo is not None else FakeCategoryReadRepository(),
    )


def test_financial_overview_aggregates_by_category_id_with_subcategories() -> None:
    overview = _service().get_financial_overview(
        account_id=1,
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 30),
    )

    assert overview.total_income == 1000
    assert overview.total_expenses == 375
    assert overview.net_change_in_period == 625

    by_id = {e.category_id: e for e in overview.expenses_by_category}
    assert set(by_id.keys()) == {10, None}

    food = by_id[10]
    # Taxonomy name wins over the row's denormalized "Food".
    assert food.category_name == "Mad & drikke"
    assert food.amount == 325

    subs = {s.subcategory_id: s for s in food.subcategories}
    assert subs[101].amount == 200
    assert subs[101].subcategory_name == "Dagligvarer"
    assert subs[102].amount == 100
    # Expense with category but no subcategory lands in the None bucket.
    assert subs[None].amount == 25
    assert subs[None].subcategory_name == "(Ingen underkategori)"

    uncategorized = by_id[None]
    assert uncategorized.category_name == "Ukategoriseret"
    assert uncategorized.amount == 50


def test_expenses_sorted_by_amount_desc() -> None:
    overview = _service().get_financial_overview(
        account_id=1,
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 30),
    )
    amounts = [e.amount for e in overview.expenses_by_category]
    assert amounts == sorted(amounts, reverse=True)


def test_unknown_category_id_falls_back_to_row_name() -> None:
    """Category id missing from the taxonomy (deleted/sync lag) keeps the
    denormalized row name instead of collapsing into Ukategoriseret."""
    overview = _service(category_repo=FakeCategoryReadRepository(categories=[])).get_financial_overview(
        account_id=1,
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 30),
    )
    by_id = {e.category_id: e for e in overview.expenses_by_category}
    assert by_id[10].category_name == "Food"


def test_overview_works_without_category_repo() -> None:
    service = AnalyticsService(FakeAnalyticsReadRepository())
    overview = service.get_financial_overview(
        account_id=1,
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 30),
    )
    assert overview.total_expenses == 375


def test_financial_overview_rejects_invalid_date_range() -> None:
    with pytest.raises(ValueError, match="Startdato"):
        _service().get_financial_overview(
            account_id=1,
            start_date=date(2026, 7, 1),
            end_date=date(2026, 6, 1),
        )


def test_list_transaction_projections_filters_by_category_and_type() -> None:
    projections = _service().list_transaction_projections(
        account_id=1,
        category_id=10,
        tx_type="expense",
    )

    assert len(projections) == 3
    groceries = projections[0]
    assert groceries.description == "Groceries"
    assert groceries.category_id == 10
    assert groceries.category_name == "Food"
    assert groceries.subcategory_id == 101
    assert groceries.subcategory_name == "Dagligvarer"


def test_list_transaction_projections_requires_account_id() -> None:
    with pytest.raises(ValueError, match="Account ID"):
        _service().list_transaction_projections(account_id=0)
