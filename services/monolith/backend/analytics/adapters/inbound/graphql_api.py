"""
GraphQL Read Gateway adapter.

This adapter functions as a cross-domain read gateway, aggregating
read-only data from multiple bounded contexts (analytics, transactions,
categories) through a single GraphQL query interface.

Architectural decision: This is a deliberate CQRS pattern where REST
handles commands (write) and GraphQL handles queries (read) across
domain boundaries. The gateway injects services from other bounded
contexts via FastAPI DI rather than accessing their repositories directly,
preserving each domain's encapsulation.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Optional

import httpx
import strawberry
from fastapi import Depends, Request
from sqlalchemy.orm import Session
from strawberry.fastapi import GraphQLRouter
from strawberry.types import Info

from backend.analytics.application.service import AnalyticsService
from backend.auth import get_account_id_from_headers
from backend.category.application.service import CategoryService
from backend.config import BUDGET_SERVICE_TIMEOUT, BUDGET_SERVICE_URL
from backend.database.mysql import get_db
from backend.dependencies import (
    get_analytics_service,
    get_category_service,
)
from backend.models.mysql.account import Account as AccountModel
from backend.shared.budget_period import budget_period, determine_budget_month

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


@strawberry.type(description="Top spending category for a given period")
class TopSpendingCategoryType:
    category_name: str
    amount: float
    percentage_of_total: float


# ---------------------------------------------------------------------------
# Context getter -- wires FastAPI DI into Strawberry resolvers
# ---------------------------------------------------------------------------


async def get_graphql_context(
    request: Request,
    db: Session = Depends(get_db),
    account_id: Optional[int] = Depends(get_account_id_from_headers),
) -> dict[str, Any]:
    """Build resolver context with hexagonal services and auth info."""
    logger.warning(
        "DEPRECATED: monolith GraphQL endpoint hit — use gateway-service. method=%s path=%s account=%s",
        request.method,
        request.url.path,
        request.headers.get("X-Account-ID", "unknown"),
    )
    return {
        "analytics_service": get_analytics_service(db),
        "category_service": get_category_service(db),
        "account_id": account_id,
        "db": db,
        "auth_header": request.headers.get("authorization", ""),
    }


def _require_account_id(ctx: dict[str, Any]) -> int:
    account_id = ctx.get("account_id")
    if not account_id:
        raise ValueError("Account ID required. Send Authorization and/or X-Account-ID header.")
    return account_id


def _get_budget_start_day(ctx: dict[str, Any], account_id: int) -> int:
    """Look up the account's configured budget start day."""
    db: Session = ctx["db"]
    row = db.query(AccountModel.budget_start_day).filter(AccountModel.idAccount == account_id).first()
    return row[0] if row and row[0] else 1


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

    @strawberry.field(description="Monthly expense totals over a period (respects budget start day)")
    def expenses_by_month(
        self,
        info: Info,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> list[MonthlyExpensesType]:
        ctx = info.context
        account_id = _require_account_id(ctx)
        service: AnalyticsService = ctx["analytics_service"]
        start_day = _get_budget_start_day(ctx, account_id)

        results = service.get_expenses_by_month(
            account_id=account_id,
            start_date=start_date,
            end_date=end_date,
            budget_start_day=start_day,
        )
        return [MonthlyExpensesType(month=r["month"], total_expenses=r["total_expenses"]) for r in results]

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
        auth_header = ctx.get("auth_header", "")

        try:
            with httpx.Client(
                timeout=BUDGET_SERVICE_TIMEOUT,
                follow_redirects=True,
            ) as client:
                resp = client.get(
                    f"{BUDGET_SERVICE_URL}/api/v1/monthly-budgets/summary",
                    params={
                        "account_id": account_id,
                        "month": month,
                        "year": year,
                        "budget_start_day": start_day,
                    },
                    headers={"Authorization": auth_header} if auth_header else {},
                )
                if resp.status_code == 401:
                    logger.warning("budget-service auth rejected (401) for budget_summary — check token forwarding")
                    return None
                resp.raise_for_status()
                data = resp.json()

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
        except httpx.ConnectError as exc:
            logger.warning("budget-service unreachable for budget_summary: %s", exc)
        except httpx.TimeoutException as exc:
            logger.warning("budget-service timeout for budget_summary: %s", exc)
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "budget-service returned %d for budget_summary: %s",
                exc.response.status_code,
                exc.response.text[:200],
            )
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning("budget-service returned unexpected payload for budget_summary: %s", exc)
        return None

    @strawberry.field(description="Financial overview for the current budget month with trend vs previous month")
    def current_month_overview(self, info: Info) -> CurrentMonthOverviewType:
        ctx = info.context
        account_id = _require_account_id(ctx)
        service: AnalyticsService = ctx["analytics_service"]
        start_day = _get_budget_start_day(ctx, account_id)

        today = date.today()
        cur_year, cur_month = determine_budget_month(today, start_day)
        start, end = budget_period(cur_year, cur_month, start_day)

        result = service.get_financial_overview(
            account_id=account_id,
            start_date=start,
            end_date=end,
        )

        prev_month = cur_month - 1 if cur_month > 1 else 12
        prev_year = cur_year if cur_month > 1 else cur_year - 1
        prev_start, prev_end = budget_period(prev_year, prev_month, start_day)

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
        start_day = _get_budget_start_day(ctx, account_id)

        start, end = budget_period(year, month, start_day)

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

    @strawberry.field(
        description="List transactions for the active account (read from MySQL projection materialised by TransactionSyncConsumer)"
    )
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
        service: AnalyticsService = ctx["analytics_service"]

        results = service.list_transaction_projections(
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
                category_id=t.category_id or 0,
                account_id=t.account_id,
                categorization_tier=t.categorization_tier,
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
