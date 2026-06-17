from __future__ import annotations

from datetime import date
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status

from app.adapters.outbound.transaction_client import HttpAnalyticsReadRepository
from app.application.dto import FinancialOverview
from app.application.service import AnalyticsService
from app.auth import get_account_id_from_headers

dashboard_router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@dashboard_router.get("/overview/", response_model=FinancialOverview)
def get_financial_overview_route(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    account_id: Optional[int] = Depends(get_account_id_from_headers),
    authorization: Optional[str] = Header(None, alias="Authorization"),
):
    if not account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account ID mangler. Vælg en konto først.",
        )
    service = AnalyticsService(read_repo=HttpAnalyticsReadRepository(authorization or ""))
    return service.get_financial_overview(account_id=account_id, start_date=start_date, end_date=end_date)


@dashboard_router.get("/expenses-by-month/", response_model=list[dict[str, Any]])
def get_expenses_by_month_route(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    account_id: Optional[int] = Depends(get_account_id_from_headers),
    authorization: Optional[str] = Header(None, alias="Authorization"),
):
    if not account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account ID mangler. Vælg en konto først.",
        )
    service = AnalyticsService(read_repo=HttpAnalyticsReadRepository(authorization or ""))
    return service.get_expenses_by_month(account_id=account_id, start_date=start_date, end_date=end_date)
