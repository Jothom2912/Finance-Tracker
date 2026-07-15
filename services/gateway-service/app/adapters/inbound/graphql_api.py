from __future__ import annotations

import logging
from datetime import date
from typing import Any, Optional

import strawberry
from domain import budget_period, determine_budget_month
from fastapi import Depends, Request
from strawberry.fastapi import GraphQLRouter
from strawberry.types import Info

from app.adapters.outbound.account_client import AccountClient
from app.adapters.outbound.analytics_client import HttpFinancialAnalyticsRepository
from app.adapters.outbound.budget_client import BudgetClient
from app.adapters.outbound.category_client import CategoryClient
from app.application.dto import CategoryExpense, TransactionProjection
from app.application.ports.outbound import (
    IAnalyticsInsightsPort,
    IFinancialAnalyticsPort,
)
from app.auth import get_account_id_from_headers

logger = logging.getLogger(__name__)


@strawberry.type(description="Expense amount for a single subcategory within a category")
class SubcategoryExpenseEntry:
    subcategory_id: Optional[int]
    subcategory_name: str
    amount: float


@strawberry.type(description="Expense amount for a single category, with subcategory breakdown")
class CategoryExpenseEntry:
    category_id: Optional[int]
    category_name: str
    amount: float
    subcategories: list[SubcategoryExpenseEntry]


def _to_expense_entries(expenses: list[CategoryExpense]) -> list[CategoryExpenseEntry]:
    return [
        CategoryExpenseEntry(
            category_id=e.category_id,
            category_name=e.category_name,
            amount=e.amount,
            subcategories=[
                SubcategoryExpenseEntry(
                    subcategory_id=s.subcategory_id,
                    subcategory_name=s.subcategory_name,
                    amount=s.amount,
                )
                for s in e.subcategories
            ],
        )
        for e in expenses
    ]


@strawberry.type(description="Financial overview for an account over a period")
class FinancialOverviewType:
    start_date: date
    end_date: date
    total_income: float
    total_expenses: float
    net_change_in_period: float
    expenses_by_category: list[CategoryExpenseEntry]
    current_account_balance: Optional[float] = None
    average_monthly_expenses: Optional[float] = None


@strawberry.type(description="Total expenses for a calendar month")
class MonthlyExpensesType:
    month: str
    total_expenses: float


@strawberry.type(description="Budget vs actual for a single category")
class BudgetSummaryItemType:
    category_id: int
    category_name: str
    budget_amount: float
    spent_amount: float
    remaining_amount: float
    percentage_used: float


@strawberry.type(description="Aggregated budget summary for a month")
class BudgetSummaryType:
    month: str
    year: str
    items: list[BudgetSummaryItemType]
    total_budget: float
    total_spent: float
    total_remaining: float
    over_budget_count: int


@strawberry.type(description="Category read projection")
class CategoryType:
    id: int
    name: str
    type: str
    display_order: int = 0


@strawberry.type(description="Subcategory read projection")
class SubcategoryType:
    id: int
    name: str
    category_id: int
    is_default: bool = True


@strawberry.type(description="Transaction read projection")
class TransactionType:
    id: int
    amount: float
    description: Optional[str]
    date: date
    type: str
    category_id: Optional[int]
    category_name: Optional[str] = None
    subcategory_id: Optional[int] = None
    subcategory_name: Optional[str] = None
    account_id: int
    categorization_tier: Optional[str] = None


@strawberry.type(description="Month-over-month trend indicators")
class TrendType:
    income_change_percent: Optional[float]
    expense_change_percent: Optional[float]
    net_change_diff: float
    previous_month_income: float
    previous_month_expenses: float


@strawberry.type(description="Current month overview with optional trend vs previous month")
class CurrentMonthOverviewType:
    start_date: date
    end_date: date
    total_income: float
    total_expenses: float
    net_change_in_period: float
    expenses_by_category: list[CategoryExpenseEntry]
    current_account_balance: Optional[float] = None
    average_monthly_expenses: Optional[float] = None
    trend: Optional[TrendType] = None


@strawberry.type(description="Top spending category for a given period")
class TopSpendingCategoryType:
    category_id: Optional[int]
    category_name: str
    amount: float
    percentage_of_total: float


@strawberry.type(
    description="Overview for one budget month — unified semantics for current AND "
    "historic months (respects budget start day; fixes the calendar/budget mismatch)"
)
class PeriodOverviewType:
    month: int
    year: int
    start_date: date
    end_date: date
    is_current: bool
    total_income: float
    total_expenses: float
    net_change_in_period: float
    expenses_by_category: list[CategoryExpenseEntry]
    current_account_balance: Optional[float] = None
    average_monthly_expenses: Optional[float] = None
    trend: Optional[TrendType] = None


@strawberry.type(description="Income vs expenses for one budget month")
class MonthlyCashflowType:
    month: str
    total_income: float
    total_expenses: float
    net: float


@strawberry.type(description="Spending change for one category between two budget months")
class CategoryDeltaType:
    category_id: Optional[int]
    category_name: str
    current_amount: float
    previous_amount: float
    change_amount: float
    change_percent: Optional[float] = None  # null = ny kategori ("Ny" i UI)


@strawberry.type(description="Month-over-month per-category spending comparison")
class MonthComparisonType:
    month: int
    year: int
    previous_month: int
    previous_year: int
    total_current: float
    total_previous: float
    deltas: list[CategoryDeltaType]


@strawberry.type(description="Paginated full-text transaction search result (danish analyzer)")
class TransactionSearchResultType:
    total_count: int
    items: list[TransactionType]


async def get_graphql_context(
    request: Request,
    account_id: Optional[int] = Depends(get_account_id_from_headers),
) -> dict[str, Any]:
    auth_header = request.headers.get("authorization", "")
    # Én ES-backed klient implementerer begge read-porte (ADR-0004);
    # nøglerne holdes adskilt så resolvers afhænger af den smalle port.
    analytics = HttpFinancialAnalyticsRepository(auth_header)
    return {
        "financial_analytics": analytics,
        "analytics_insights": analytics,
        "account_client": AccountClient(auth_header),
        "budget_client": BudgetClient(auth_header),
        "category_client": CategoryClient(auth_header),
        "account_id": account_id,
        "auth_header": auth_header,
        "_budget_start_day_cache": {},
    }


def _require_account_id(ctx: dict[str, Any]) -> int:
    account_id = ctx.get("account_id")
    if not account_id:
        raise ValueError("Account ID required. Send Authorization and/or X-Account-ID header.")
    return account_id


def _get_budget_start_day(ctx: dict[str, Any], account_id: int) -> int:
    cache = ctx["_budget_start_day_cache"]
    if account_id in cache:
        return cache[account_id]
    client: AccountClient = ctx["account_client"]
    value = client.get_budget_start_day(account_id)
    cache[account_id] = value
    return value


def _to_transaction_type(t: TransactionProjection) -> TransactionType:
    return TransactionType(
        id=t.id,
        amount=t.amount,
        description=t.description,
        date=t.date,
        type=t.type,
        category_id=t.category_id,
        category_name=t.category_name,
        subcategory_id=t.subcategory_id,
        subcategory_name=t.subcategory_name,
        account_id=t.account_id,
        categorization_tier=t.categorization_tier,
    )


def _pct_change(current: float, previous: float) -> float | None:
    if previous == 0:
        return None
    return round(((current - previous) / abs(previous)) * 100, 1)


def _build_trend(result: Any, prev_result: Any) -> TrendType:
    return TrendType(
        income_change_percent=_pct_change(result.total_income, prev_result.total_income),
        expense_change_percent=_pct_change(result.total_expenses, prev_result.total_expenses),
        net_change_diff=round(result.net_change_in_period - prev_result.net_change_in_period, 2),
        previous_month_income=prev_result.total_income,
        previous_month_expenses=prev_result.total_expenses,
    )


def _overview_with_trend(
    ctx: dict[str, Any], account_id: int, year: int, month: int
) -> tuple[Any, TrendType, date, date]:
    """Budgetmåneds-overview + trend mod forrige budgetmåned — fælles
    motor for periodOverview (vilkårlig måned) og currentMonthOverview."""
    port: IFinancialAnalyticsPort = ctx["financial_analytics"]
    start_day = _get_budget_start_day(ctx, account_id)

    start, end = budget_period(year, month, start_day)
    result = port.get_financial_overview(account_id=account_id, start_date=start, end_date=end)

    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    prev_start, prev_end = budget_period(prev_year, prev_month, start_day)
    prev_result = port.get_financial_overview(account_id=account_id, start_date=prev_start, end_date=prev_end)

    return result, _build_trend(result, prev_result), start, end


@strawberry.type(description="Read-only queries across Finance Tracker domains")
class Query:
    @strawberry.field(description="Financial overview for the active account")
    def financial_overview(
        self,
        info: Info,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> FinancialOverviewType:
        ctx = info.context
        account_id = _require_account_id(ctx)
        port: IFinancialAnalyticsPort = ctx["financial_analytics"]

        result = port.get_financial_overview(
            account_id=account_id,
            start_date=start_date,
            end_date=end_date,
        )

        return FinancialOverviewType(
            start_date=result.start_date,
            end_date=result.end_date,
            total_income=result.total_income,
            total_expenses=result.total_expenses,
            net_change_in_period=result.net_change_in_period,
            expenses_by_category=_to_expense_entries(result.expenses_by_category),
            current_account_balance=result.current_account_balance,
            average_monthly_expenses=result.average_monthly_expenses,
        )

    @strawberry.field(description="Monthly expense totals over a period (respects budget start day)")
    def expenses_by_month(
        self,
        info: Info,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> list[MonthlyExpensesType]:
        ctx = info.context
        account_id = _require_account_id(ctx)
        port: IFinancialAnalyticsPort = ctx["financial_analytics"]
        start_day = _get_budget_start_day(ctx, account_id)

        results = port.get_expenses_by_month(
            account_id=account_id,
            start_date=start_date,
            end_date=end_date,
            budget_start_day=start_day,
        )
        return [MonthlyExpensesType(month=r.month, total_expenses=r.total_expenses) for r in results]

    @strawberry.field(description="Budget summary for a specific month (proxied to budget-service)")
    def budget_summary(
        self,
        info: Info,
        month: int,
        year: int,
    ) -> Optional[BudgetSummaryType]:
        ctx = info.context
        account_id = _require_account_id(ctx)
        start_day = _get_budget_start_day(ctx, account_id)
        budget_client: BudgetClient = ctx["budget_client"]

        data = budget_client.get_budget_summary(
            account_id=account_id,
            month=month,
            year=year,
            budget_start_day=start_day,
        )
        if data is None:
            return None

        return BudgetSummaryType(
            month=str(data["month"]).zfill(2),
            year=str(data["year"]),
            items=[
                BudgetSummaryItemType(
                    category_id=item["category_id"],
                    category_name=item["category_name"],
                    budget_amount=item["budget_amount"],
                    spent_amount=item["spent_amount"],
                    remaining_amount=item["remaining_amount"],
                    percentage_used=item["percentage_used"],
                )
                for item in data.get("items", [])
            ],
            total_budget=data["total_budget"],
            total_spent=data["total_spent"],
            total_remaining=data["total_remaining"],
            over_budget_count=data["over_budget_count"],
        )

    @strawberry.field(
        description="Overview for any budget month with trend vs the previous one. "
        "Unifies current/historic semantics: the period always follows the account's "
        "budget start day"
    )
    def period_overview(self, info: Info, month: int, year: int) -> PeriodOverviewType:
        ctx = info.context
        account_id = _require_account_id(ctx)
        start_day = _get_budget_start_day(ctx, account_id)

        result, trend, start, end = _overview_with_trend(ctx, account_id, year, month)
        is_current = determine_budget_month(date.today(), start_day) == (year, month)

        return PeriodOverviewType(
            month=month,
            year=year,
            start_date=start,
            end_date=end,
            is_current=is_current,
            total_income=result.total_income,
            total_expenses=result.total_expenses,
            net_change_in_period=result.net_change_in_period,
            expenses_by_category=_to_expense_entries(result.expenses_by_category),
            current_account_balance=result.current_account_balance,
            average_monthly_expenses=result.average_monthly_expenses,
            trend=trend,
        )

    @strawberry.field(description="Financial overview for the current budget month with trend vs previous month")
    def current_month_overview(self, info: Info) -> CurrentMonthOverviewType:
        ctx = info.context
        account_id = _require_account_id(ctx)
        start_day = _get_budget_start_day(ctx, account_id)

        cur_year, cur_month = determine_budget_month(date.today(), start_day)
        result, trend, _, _ = _overview_with_trend(ctx, account_id, cur_year, cur_month)

        return CurrentMonthOverviewType(
            start_date=result.start_date,
            end_date=result.end_date,
            total_income=result.total_income,
            total_expenses=result.total_expenses,
            net_change_in_period=result.net_change_in_period,
            expenses_by_category=_to_expense_entries(result.expenses_by_category),
            current_account_balance=result.current_account_balance,
            average_monthly_expenses=result.average_monthly_expenses,
            trend=trend,
        )

    @strawberry.field(
        description="Income vs expenses per budget month, dense window ending at the "
        "current budget month (analytics read-side)"
    )
    def cashflow_by_month(self, info: Info, months: int = 12) -> list[MonthlyCashflowType]:
        ctx = info.context
        account_id = _require_account_id(ctx)
        insights: IAnalyticsInsightsPort = ctx["analytics_insights"]
        start_day = _get_budget_start_day(ctx, account_id)

        rows = insights.get_cashflow_by_month(account_id=account_id, months=months, budget_start_day=start_day)
        return [
            MonthlyCashflowType(
                month=r.month,
                total_income=r.total_income,
                total_expenses=r.total_expenses,
                net=r.net,
            )
            for r in rows
        ]

    @strawberry.field(
        description="Largest per-category spending changes vs the previous budget month (analytics read-side)"
    )
    def month_comparison(self, info: Info, month: int, year: int, limit: int = 5) -> MonthComparisonType:
        ctx = info.context
        account_id = _require_account_id(ctx)
        insights: IAnalyticsInsightsPort = ctx["analytics_insights"]
        start_day = _get_budget_start_day(ctx, account_id)

        result = insights.get_month_comparison(
            account_id=account_id, year=year, month=month, budget_start_day=start_day
        )
        return MonthComparisonType(
            month=result.month,
            year=result.year,
            previous_month=result.previous_month,
            previous_year=result.previous_year,
            total_current=result.total_current,
            total_previous=result.total_previous,
            deltas=[
                CategoryDeltaType(
                    category_id=d.category_id,
                    category_name=d.category_name,
                    current_amount=d.current_amount,
                    previous_amount=d.previous_amount,
                    change_amount=d.change_amount,
                    change_percent=d.change_percent,
                )
                for d in result.deltas[:limit]
            ],
        )

    @strawberry.field(description="Full-text transaction search (danish analyzer, analytics read-side)")
    def search_transactions(
        self,
        info: Info,
        query: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        category_id: Optional[int] = None,
        tx_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> TransactionSearchResultType:
        ctx = info.context
        account_id = _require_account_id(ctx)
        insights: IAnalyticsInsightsPort = ctx["analytics_insights"]

        total_count, items = insights.search_transactions(
            account_id=account_id,
            query=query,
            start_date=start_date,
            end_date=end_date,
            category_id=category_id,
            tx_type=tx_type,
            limit=limit,
            offset=offset,
        )
        return TransactionSearchResultType(
            total_count=total_count,
            items=[_to_transaction_type(t) for t in items],
        )

    @strawberry.field(description="Top spending categories for a month")
    def top_spending_categories(
        self,
        info: Info,
        month: int,
        year: int,
        limit: int = 5,
    ) -> list[TopSpendingCategoryType]:
        ctx = info.context
        account_id = _require_account_id(ctx)
        port: IFinancialAnalyticsPort = ctx["financial_analytics"]
        start_day = _get_budget_start_day(ctx, account_id)

        start, end = budget_period(year, month, start_day)

        result = port.get_financial_overview(account_id=account_id, start_date=start, end_date=end)

        total = result.total_expenses or 1.0
        # expenses_by_category is already sorted by amount desc.
        return [
            TopSpendingCategoryType(
                category_id=e.category_id,
                category_name=e.category_name,
                amount=e.amount,
                percentage_of_total=round((e.amount / total) * 100, 1),
            )
            for e in result.expenses_by_category[:limit]
        ]

    @strawberry.field(description="List all categories (from categorization-service, ADR-003)")
    def categories(self, info: Info) -> list[CategoryType]:
        ctx = info.context
        client: CategoryClient = ctx["category_client"]
        cats = client.get_categories()
        return [
            CategoryType(
                id=c.get("id", 0),
                name=c.get("name", ""),
                type=c.get("type", ""),
                display_order=c.get("display_order", 0),
            )
            for c in cats
        ]

    @strawberry.field(description="List subcategories, optionally filtered by category")
    def subcategories(self, info: Info, category_id: Optional[int] = None) -> list[SubcategoryType]:
        ctx = info.context
        client: CategoryClient = ctx["category_client"]
        subs = client.get_subcategories()
        if category_id is not None:
            subs = [s for s in subs if s.get("category_id") == category_id]
        return [
            SubcategoryType(
                id=s.get("id", 0),
                name=s.get("name", ""),
                category_id=s.get("category_id", 0),
                is_default=s.get("is_default", True),
            )
            for s in subs
        ]

    @strawberry.field(
        description="List transactions for the active account. month/year (budget month, "
        "respects budget start day) and start_date/end_date are mutually exclusive — "
        "month/year wins when both are provided"
    )
    def transactions(
        self,
        info: Info,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        month: Optional[int] = None,
        year: Optional[int] = None,
        category_id: Optional[int] = None,
        tx_type: Optional[str] = None,
        limit: int = 100,
    ) -> list[TransactionType]:
        ctx = info.context
        account_id = _require_account_id(ctx)
        port: IFinancialAnalyticsPort = ctx["financial_analytics"]

        if month is not None and year is not None:
            start_day = _get_budget_start_day(ctx, account_id)
            start_date, end_date = budget_period(year, month, start_day)

        results = port.list_transactions(
            account_id=account_id,
            start_date=start_date,
            end_date=end_date,
            category_id=category_id,
            tx_type=tx_type,
            limit=limit,
        )
        return [_to_transaction_type(t) for t in results]


schema = strawberry.Schema(query=Query)


def create_graphql_router() -> GraphQLRouter:
    return GraphQLRouter(schema, context_getter=get_graphql_context)
