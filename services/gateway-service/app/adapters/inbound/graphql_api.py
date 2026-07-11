from __future__ import annotations

import logging
from datetime import date
from typing import Any, Optional

import strawberry
from fastapi import Depends, Request
from strawberry.fastapi import GraphQLRouter
from strawberry.types import Info

from app.adapters.outbound.account_client import AccountClient
from app.adapters.outbound.analytics_client import HttpFinancialAnalyticsRepository
from app.adapters.outbound.budget_client import BudgetClient
from app.adapters.outbound.category_client import CategoryClient
from app.adapters.outbound.dual_read_analytics import DualReadFinancialAnalyticsRepository
from app.adapters.outbound.legacy_analytics_adapter import LegacyFinancialAnalyticsAdapter
from app.adapters.outbound.transaction_client import HttpAnalyticsReadRepository
from app.application.dto import CategoryExpense
from app.application.ports.outbound import IFinancialAnalyticsPort
from app.application.service import AnalyticsService
from app.auth import get_account_id_from_headers
from app.config import ANALYTICS_READ_SOURCE
from app.shared.budget_period import budget_period, determine_budget_month

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


def build_financial_analytics_port(
    auth_header: str,
    read_source: str = ANALYTICS_READ_SOURCE,
) -> IFinancialAnalyticsPort:
    """Vælger read-side implementering ud fra ANALYTICS_READ_SOURCE:
    legacy | dual | analytics (cutover = env-flip, ingen kodeændring)."""
    if read_source == "analytics":
        return HttpFinancialAnalyticsRepository(auth_header)

    legacy = LegacyFinancialAnalyticsAdapter(
        AnalyticsService(
            read_repo=HttpAnalyticsReadRepository(auth_header),
            category_repo=CategoryClient(auth_header),
        )
    )
    if read_source == "dual":
        return DualReadFinancialAnalyticsRepository(
            primary=legacy,
            shadow=HttpFinancialAnalyticsRepository(auth_header),
        )
    return legacy


async def get_graphql_context(
    request: Request,
    account_id: Optional[int] = Depends(get_account_id_from_headers),
) -> dict[str, Any]:
    auth_header = request.headers.get("authorization", "")
    category_client = CategoryClient(auth_header)
    return {
        "financial_analytics": build_financial_analytics_port(auth_header),
        "account_client": AccountClient(auth_header),
        "budget_client": BudgetClient(auth_header),
        "category_client": category_client,
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

    @strawberry.field(description="Financial overview for the current budget month with trend vs previous month")
    def current_month_overview(self, info: Info) -> CurrentMonthOverviewType:
        ctx = info.context
        account_id = _require_account_id(ctx)
        port: IFinancialAnalyticsPort = ctx["financial_analytics"]
        start_day = _get_budget_start_day(ctx, account_id)

        today = date.today()
        cur_year, cur_month = determine_budget_month(today, start_day)
        start, end = budget_period(cur_year, cur_month, start_day)

        result = port.get_financial_overview(
            account_id=account_id,
            start_date=start,
            end_date=end,
        )

        prev_month = cur_month - 1 if cur_month > 1 else 12
        prev_year = cur_year if cur_month > 1 else cur_year - 1
        prev_start, prev_end = budget_period(prev_year, prev_month, start_day)

        prev_result = port.get_financial_overview(
            account_id=account_id,
            start_date=prev_start,
            end_date=prev_end,
        )

        def _pct_change(current: float, previous: float) -> float | None:
            if previous == 0:
                return None
            return round(((current - previous) / abs(previous)) * 100, 1)

        trend = TrendType(
            income_change_percent=_pct_change(result.total_income, prev_result.total_income),
            expense_change_percent=_pct_change(result.total_expenses, prev_result.total_expenses),
            net_change_diff=round(result.net_change_in_period - prev_result.net_change_in_period, 2),
            previous_month_income=prev_result.total_income,
            previous_month_expenses=prev_result.total_expenses,
        )

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

    @strawberry.field(description="List transactions for the active account")
    def transactions(
        self,
        info: Info,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        category_id: Optional[int] = None,
        tx_type: Optional[str] = None,
        limit: int = 100,
    ) -> list[TransactionType]:
        ctx = info.context
        account_id = _require_account_id(ctx)
        port: IFinancialAnalyticsPort = ctx["financial_analytics"]

        results = port.list_transactions(
            account_id=account_id,
            start_date=start_date,
            end_date=end_date,
            category_id=category_id,
            tx_type=tx_type,
            limit=limit,
        )
        return [
            TransactionType(
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
            for t in results
        ]


schema = strawberry.Schema(query=Query)


def create_graphql_router() -> GraphQLRouter:
    return GraphQLRouter(schema, context_getter=get_graphql_context)
