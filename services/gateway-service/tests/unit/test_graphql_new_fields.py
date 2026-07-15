"""Nye analytics-backede GraphQL-felter + skema-bagudkompatibilitet."""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from app.adapters.inbound.graphql_api import schema
from app.application.dto import (
    CategoryDelta,
    FinancialOverview,
    MonthComparison,
    MonthlyCashflow,
    TransactionProjection,
)
from domain import determine_budget_month


class FakeFinancialPort:
    def __init__(self) -> None:
        self.calls: list[tuple[int, Optional[date], Optional[date]]] = []

    def get_financial_overview(self, account_id, start_date=None, end_date=None):
        self.calls.append((account_id, start_date, end_date))
        # Nuværende periode: 1000/375; forrige: 500/750 → trend beregnes.
        first_call = len(self.calls) == 1
        return FinancialOverview(
            start_date=start_date,
            end_date=end_date,
            total_income=1000.0 if first_call else 500.0,
            total_expenses=375.0 if first_call else 750.0,
            net_change_in_period=625.0 if first_call else -250.0,
            expenses_by_category=[],
            current_account_balance=625.0,
            average_monthly_expenses=375.0,
        )

    def get_expenses_by_month(self, *args: Any, **kwargs: Any):
        return []

    def list_transactions(self, account_id, start_date=None, end_date=None, category_id=None, tx_type=None, limit=100):
        self.last_range = (start_date, end_date)
        return [
            TransactionProjection(
                id=1,
                amount=100.0,
                description="Netto",
                date=date(2026, 6, 2),
                type="expense",
                category_id=10,
                account_id=account_id,
            )
        ]


class FakeInsightsPort:
    def get_cashflow_by_month(self, account_id, months=12, budget_start_day=1):
        self.cashflow_args = (account_id, months, budget_start_day)
        return [
            MonthlyCashflow(month="2026-05", total_income=0.0, total_expenses=0.0, net=0.0),
            MonthlyCashflow(month="2026-06", total_income=1000.0, total_expenses=375.0, net=625.0),
        ]

    def get_month_comparison(self, account_id, year, month, budget_start_day=1):
        return MonthComparison(
            month=month,
            year=year,
            previous_month=month - 1 if month > 1 else 12,
            previous_year=year if month > 1 else year - 1,
            total_current=375.0,
            total_previous=100.0,
            deltas=[
                CategoryDelta(
                    category_id=10,
                    category_name="Mad & drikke",
                    current_amount=325.0,
                    previous_amount=100.0,
                    change_amount=225.0,
                    change_percent=225.0,
                ),
                CategoryDelta(
                    category_id=None,
                    category_name="Ukategoriseret",
                    current_amount=50.0,
                    previous_amount=0.0,
                    change_amount=50.0,
                    change_percent=None,
                ),
                CategoryDelta(
                    category_id=11,
                    category_name="Transport",
                    current_amount=10.0,
                    previous_amount=5.0,
                    change_amount=5.0,
                    change_percent=100.0,
                ),
            ],
        )

    def search_transactions(self, account_id, query, **kwargs: Any):
        self.search_args = (account_id, query, kwargs)
        return 42, [
            TransactionProjection(
                id=7,
                amount=250.0,
                description="Tryg forsikring",
                date=date(2026, 6, 15),
                type="expense",
                category_id=None,
                account_id=account_id,
            )
        ]


def make_context(budget_start_day: int = 1) -> dict[str, Any]:
    return {
        "financial_analytics": FakeFinancialPort(),
        "analytics_insights": FakeInsightsPort(),
        "account_id": 1,
        "auth_header": "",
        "_budget_start_day_cache": {1: budget_start_day},
    }


def execute(query: str, ctx: dict[str, Any]):
    result = schema.execute_sync(query, context_value=ctx)
    assert result.errors is None, result.errors
    return result.data


class TestSchemaBackCompat:
    def test_existing_fields_are_unchanged(self) -> None:
        sdl = str(schema)
        for field in (
            "financialOverview",
            "expensesByMonth",
            "budgetSummary",
            "currentMonthOverview",
            "topSpendingCategories",
            "categories",
            "subcategories",
            "transactions",
        ):
            assert field in sdl, f"eksisterende felt {field} mangler i skemaet"

    def test_new_fields_are_exposed(self) -> None:
        sdl = str(schema)
        for field in ("periodOverview", "cashflowByMonth", "monthComparison", "searchTransactions"):
            assert field in sdl, f"nyt felt {field} mangler i skemaet"


class TestPeriodOverview:
    QUERY = """
    { periodOverview(month: %d, year: %d) {
        month year startDate endDate isCurrent
        totalIncome totalExpenses netChangeInPeriod
        trend { incomeChangePercent expenseChangePercent netChangeDiff }
    } }
    """

    def test_historic_month_has_trend_and_is_not_current(self) -> None:
        data = execute(self.QUERY % (2, 2026), make_context())
        overview = data["periodOverview"]

        assert overview["isCurrent"] is False
        assert overview["startDate"] == "2026-02-01"
        assert overview["endDate"] == "2026-02-28"
        assert overview["trend"]["incomeChangePercent"] == 100.0  # 1000 vs 500
        assert overview["trend"]["expenseChangePercent"] == -50.0  # 375 vs 750
        assert overview["trend"]["netChangeDiff"] == 875.0

    def test_current_budget_month_is_marked_current(self) -> None:
        year, month = determine_budget_month(date.today(), 1)
        data = execute(self.QUERY % (month, year), make_context())
        assert data["periodOverview"]["isCurrent"] is True

    def test_january_trend_compares_against_december_last_year(self) -> None:
        ctx = make_context()
        execute(self.QUERY % (1, 2026), ctx)
        calls = ctx["financial_analytics"].calls
        assert calls[0][1] == date(2026, 1, 1)  # nuværende periode
        assert calls[1][1] == date(2025, 12, 1)  # forrige = december året før

    def test_respects_budget_start_day(self) -> None:
        ctx = make_context(budget_start_day=26)
        data = execute(self.QUERY % (7, 2026), ctx)
        assert data["periodOverview"]["startDate"] == "2026-06-26"
        assert data["periodOverview"]["endDate"] == "2026-07-25"


class TestCashflowByMonth:
    def test_returns_rows_and_passes_budget_start_day(self) -> None:
        ctx = make_context(budget_start_day=15)
        data = execute("{ cashflowByMonth(months: 2) { month totalIncome totalExpenses net } }", ctx)

        assert [r["month"] for r in data["cashflowByMonth"]] == ["2026-05", "2026-06"]
        assert data["cashflowByMonth"][1]["net"] == 625.0
        assert ctx["analytics_insights"].cashflow_args == (1, 2, 15)


class TestMonthComparison:
    def test_limit_truncates_deltas(self) -> None:
        data = execute(
            "{ monthComparison(month: 6, year: 2026, limit: 2) { totalCurrent deltas { categoryName changePercent } } }",
            make_context(),
        )
        comparison = data["monthComparison"]
        assert comparison["totalCurrent"] == 375.0
        assert len(comparison["deltas"]) == 2
        # Ny kategori har changePercent = null ("Ny" i UI).
        assert comparison["deltas"][1]["changePercent"] is None


class TestSearchTransactions:
    def test_returns_total_count_and_items(self) -> None:
        ctx = make_context()
        data = execute(
            '{ searchTransactions(query: "forsikring", limit: 10, offset: 0) { totalCount items { id description } } }',
            ctx,
        )
        result = data["searchTransactions"]
        assert result["totalCount"] == 42
        assert result["items"][0]["description"] == "Tryg forsikring"
        account_id, query, kwargs = ctx["analytics_insights"].search_args
        assert (account_id, query, kwargs["limit"]) == (1, "forsikring", 10)


class TestTransactionsMonthArgs:
    def test_month_year_maps_to_budget_period(self) -> None:
        ctx = make_context(budget_start_day=26)
        execute("{ transactions(month: 7, year: 2026, limit: 10) { id } }", ctx)
        assert ctx["financial_analytics"].last_range == (date(2026, 6, 26), date(2026, 7, 25))

    def test_explicit_dates_still_work(self) -> None:
        ctx = make_context()
        execute('{ transactions(startDate: "2026-06-01", endDate: "2026-06-30") { id } }', ctx)
        assert ctx["financial_analytics"].last_range == (date(2026, 6, 1), date(2026, 6, 30))
