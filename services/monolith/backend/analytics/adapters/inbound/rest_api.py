"""
REST API adapter for Analytics bounded context.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.analytics.application.dto import FinancialOverview
from backend.analytics.application.service import AnalyticsService
from backend.auth import get_account_id_from_headers
from backend.dependencies import get_analytics_service

dashboard_router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


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
    return service.get_financial_overview(account_id=account_id, start_date=start_date, end_date=end_date)


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
    return service.get_expenses_by_month(account_id=account_id, start_date=start_date, end_date=end_date)
