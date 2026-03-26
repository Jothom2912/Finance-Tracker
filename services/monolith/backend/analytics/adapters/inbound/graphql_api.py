"""
GraphQL Read Gateway adapter.

This adapter functions as a cross-domain read gateway, aggregating
read-only data from multiple bounded contexts (analytics, transactions,
categories, goals) through a single GraphQL query interface.

Architectural decision: This is a deliberate CQRS pattern where REST
handles commands (write) and GraphQL handles queries (read) across
domain boundaries. The gateway injects services from other bounded
contexts via FastAPI DI rather than accessing their repositories directly,
preserving each domain's encapsulation.
"""

from __future__ import annotations

import logging
from calendar import monthrange
from datetime import date
from typing import Any, Optional

import strawberry
from fastapi import Depends
from sqlalchemy.orm import Session
from strawberry.fastapi import GraphQLRouter
from strawberry.types import Info

from backend.analytics.application.service import AnalyticsService
from backend.auth import get_account_id_from_headers
from backend.category.application.service import CategoryService
from backend.database.mysql import get_db
from backend.dependencies import (
    get_analytics_service,
    get_category_service,
    get_goal_service,
    get_monthly_budget_service,
    get_transaction_service,
)
from backend.goal.application.service import GoalService
from backend.monthly_budget.application.service import MonthlyBudgetService
from backend.transaction.application.service import TransactionService

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Strawberry types (read-only projections)
# ---------------------------------------------------------------------------


@strawberry.type(description="Expense amount for a single category")
class CategoryExpenseEntry:
    category_name: str
    amount: float


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


@strawberry.type(description="Transaction read projection")
class TransactionType:
    id: int
    amount: float
    description: Optional[str]
    date: date
    type: str
    category_id: int
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


@strawberry.type(description="Goal progress read projection")
class GoalProgressType:
    id: int
    name: Optional[str]
    target_amount: float
    current_amount: float
    target_date: Optional[date]
    status: Optional[str]
    percent_complete: float


@strawberry.type(description="Top spending category for a given period")
class TopSpendingCategoryType:
    category_name: str
    amount: float
    percentage_of_total: float


# ---------------------------------------------------------------------------
# Context getter -- wires FastAPI DI into Strawberry resolvers
# ---------------------------------------------------------------------------


async def get_graphql_context(
    db: Session = Depends(get_db),
    account_id: Optional[int] = Depends(get_account_id_from_headers),
) -> dict[str, Any]:
    """Build resolver context with hexagonal services and auth info."""
    return {
        "analytics_service": get_analytics_service(db),
        "category_service": get_category_service(db),
        "goal_service": get_goal_service(db),
        "monthly_budget_service": get_monthly_budget_service(db),
        "transaction_service": get_transaction_service(db),
        "account_id": account_id,
    }


def _require_account_id(ctx: dict[str, Any]) -> int:
    account_id = ctx.get("account_id")
    if not account_id:
        raise ValueError("Account ID required. Send Authorization and/or X-Account-ID header.")
    return account_id


# ---------------------------------------------------------------------------
# Query root
# ---------------------------------------------------------------------------


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
        service: AnalyticsService = ctx["analytics_service"]

        result = service.get_financial_overview(
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
            expenses_by_category=[
                CategoryExpenseEntry(category_name=name, amount=amount)
                for name, amount in result.expenses_by_category.items()
            ],
            current_account_balance=result.current_account_balance,
            average_monthly_expenses=result.average_monthly_expenses,
        )

    @strawberry.field(description="Monthly expense totals over a period")
    def expenses_by_month(
        self,
        info: Info,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> list[MonthlyExpensesType]:
        ctx = info.context
        account_id = _require_account_id(ctx)
        service: AnalyticsService = ctx["analytics_service"]

        results = service.get_expenses_by_month(
            account_id=account_id,
            start_date=start_date,
            end_date=end_date,
        )
        return [MonthlyExpensesType(month=r["month"], total_expenses=r["total_expenses"]) for r in results]

    @strawberry.field(description="Budget summary for a specific month")
    def budget_summary(
        self,
        info: Info,
        month: int,
        year: int,
    ) -> BudgetSummaryType:
        ctx = info.context
        account_id = _require_account_id(ctx)
        mb_service: MonthlyBudgetService = ctx["monthly_budget_service"]

        result = mb_service.get_summary(account_id=account_id, month=month, year=year)
        return BudgetSummaryType(
            month=str(result.month).zfill(2),
            year=str(result.year),
            items=[
                BudgetSummaryItemType(
                    category_id=item.category_id,
                    category_name=item.category_name,
                    budget_amount=item.budget_amount,
                    spent_amount=item.spent_amount,
                    remaining_amount=item.remaining_amount,
                    percentage_used=item.percentage_used,
                )
                for item in result.items
            ],
            total_budget=result.total_budget,
            total_spent=result.total_spent,
            total_remaining=result.total_remaining,
            over_budget_count=result.over_budget_count,
        )

    @strawberry.field(description="Financial overview for the current calendar month with trend vs previous month")
    def current_month_overview(self, info: Info) -> CurrentMonthOverviewType:
        ctx = info.context
        account_id = _require_account_id(ctx)
        service: AnalyticsService = ctx["analytics_service"]

        today = date.today()
        start = date(today.year, today.month, 1)
        _, last_day = monthrange(today.year, today.month)
        end = date(today.year, today.month, last_day)

        result = service.get_financial_overview(
            account_id=account_id,
            start_date=start,
            end_date=end,
        )

        prev_year = today.year if today.month > 1 else today.year - 1
        prev_month = today.month - 1 if today.month > 1 else 12
        prev_start = date(prev_year, prev_month, 1)
        _, prev_last_day = monthrange(prev_year, prev_month)
        prev_end = date(prev_year, prev_month, prev_last_day)

        prev_result = service.get_financial_overview(
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
            expenses_by_category=[
                CategoryExpenseEntry(category_name=name, amount=amount)
                for name, amount in result.expenses_by_category.items()
            ],
            current_account_balance=result.current_account_balance,
            average_monthly_expenses=result.average_monthly_expenses,
            trend=trend,
        )

    @strawberry.field(description="Progress for all goals on the active account")
    def goal_progress(self, info: Info) -> list[GoalProgressType]:
        ctx = info.context
        account_id = _require_account_id(ctx)
        goal_service: GoalService = ctx["goal_service"]

        goals = goal_service.list_goals(account_id=account_id)
        return [
            GoalProgressType(
                id=g.idGoal,
                name=g.name,
                target_amount=g.target_amount,
                current_amount=g.current_amount,
                target_date=g.target_date,
                status=g.status,
                percent_complete=(
                    round((g.current_amount / g.target_amount) * 100, 1) if g.target_amount > 0 else 100.0
                ),
            )
            for g in goals
        ]

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
        service: AnalyticsService = ctx["analytics_service"]

        start = date(year, month, 1)
        _, last_day = monthrange(year, month)
        end = date(year, month, last_day)

        result = service.get_financial_overview(account_id=account_id, start_date=start, end_date=end)

        total = result.total_expenses or 1.0
        sorted_cats = sorted(result.expenses_by_category.items(), key=lambda x: x[1], reverse=True)[:limit]

        return [
            TopSpendingCategoryType(
                category_name=name,
                amount=amount,
                percentage_of_total=round((amount / total) * 100, 1),
            )
            for name, amount in sorted_cats
        ]

    # -- Cross-context read resolvers (thin gateway layer) --

    @strawberry.field(description="List all categories")
    def categories(self, info: Info) -> list[CategoryType]:
        service: CategoryService = info.context["category_service"]
        results = service.list_categories()
        return [CategoryType(id=c.idCategory, name=c.name, type=c.type) for c in results]

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
        service: TransactionService = ctx["transaction_service"]

        results = service.list_transactions(
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
                account_id=t.account_id,
                categorization_tier=getattr(t, "categorization_tier", None),
            )
            for t in results
        ]


# ---------------------------------------------------------------------------
# Schema & router factory
# ---------------------------------------------------------------------------

schema = strawberry.Schema(query=Query)


def create_graphql_router() -> GraphQLRouter:
    """Create a Strawberry GraphQLRouter with DI context."""
    return GraphQLRouter(schema, context_getter=get_graphql_context)
