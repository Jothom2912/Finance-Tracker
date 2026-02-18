"""
REST API adapter for Analytics bounded context.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.analytics.application.service import AnalyticsService
from backend.auth import get_account_id_from_headers
from backend.dependencies import get_analytics_service
from backend.shared.schemas.budget import BudgetSummary
from backend.shared.schemas.dashboard import FinancialOverview

dashboard_router = APIRouter(prefix="/dashboard", tags=["Dashboard"])
budget_summary_router = APIRouter(prefix="/budgets", tags=["Budgets"])


@dashboard_router.get("/overview/", response_model=FinancialOverview)
def get_financial_overview_route(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    service: AnalyticsService = Depends(get_analytics_service),
    account_id: Optional[int] = Depends(get_account_id_from_headers),
):
    if not account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account ID mangler. Vælg en konto først.",
        )
    return service.get_financial_overview(
        account_id=account_id, start_date=start_date, end_date=end_date
    )


@dashboard_router.get("/expenses-by-month/", response_model=list[dict[str, Any]])
def get_expenses_by_month_route(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    service: AnalyticsService = Depends(get_analytics_service),
    account_id: Optional[int] = Depends(get_account_id_from_headers),
):
    if not account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account ID mangler. Vælg en konto først.",
        )
    return service.get_expenses_by_month(
        account_id=account_id, start_date=start_date, end_date=end_date
    )


@budget_summary_router.get("/summary", response_model=BudgetSummary)
async def get_budget_summary_route(
    month: str = Query(..., description="Month (1-12)."),
    year: str = Query(..., description="Year (YYYY format)."),
    service: AnalyticsService = Depends(get_analytics_service),
    account_id: Optional[int] = Depends(get_account_id_from_headers),
):
    if not account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account ID mangler. Vælg en konto først.",
        )

    try:
        month_int = int(month)
        year_int = int(year)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Ugyldige værdier: month og year skal være heltal. "
                f"Fik month={month}, year={year}"
            ),
        )

    if month_int < 1 or month_int > 12:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Month skal være mellem 1 og 12. Fik: {month_int}",
        )
    if year_int < 2000 or year_int > 9999:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Year skal være mellem 2000 og 9999. Fik: {year_int}",
        )

    return service.get_budget_summary(
        account_id=account_id, month=month_int, year=year_int
    )
