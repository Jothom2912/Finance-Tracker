"""REST-adapter: /api/v1/analytics/* med JWT-auth og domain-fejl-mapping."""

from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from elasticsearch import AsyncElasticsearch
from fastapi import APIRouter, Depends, Query, Request

from app.adapters.outbound.elasticsearch.query_store import EsAnalyticsQueryStore
from app.application.dto import (
    FinancialOverviewDTO,
    MonthComparisonDTO,
    MonthlyCashflowDTO,
    MonthlyExpensesDTO,
    TopMerchantDTO,
    TransactionSearchResultDTO,
)
from app.application.query_service import AnalyticsQueryService
from app.auth import get_current_user_id
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


def get_query_service(request: Request) -> AnalyticsQueryService:
    es: AsyncElasticsearch = request.app.state.es
    return AnalyticsQueryService(EsAnalyticsQueryStore(es, settings.es_index_prefix))


@router.get("/overview", response_model=FinancialOverviewDTO)
async def overview(
    account_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    user_id: int = Depends(get_current_user_id),
    service: AnalyticsQueryService = Depends(get_query_service),
) -> FinancialOverviewDTO:
    return await service.financial_overview(
        user_id=user_id, account_id=account_id, start_date=start_date, end_date=end_date
    )


@router.get("/expenses-by-month", response_model=list[MonthlyExpensesDTO])
async def expenses_by_month(
    account_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    budget_start_day: Optional[int] = Query(default=None, ge=1, le=28),
    user_id: int = Depends(get_current_user_id),
    service: AnalyticsQueryService = Depends(get_query_service),
) -> list[MonthlyExpensesDTO]:
    return await service.expenses_by_month(
        user_id=user_id,
        account_id=account_id,
        start_date=start_date,
        end_date=end_date,
        budget_start_day=budget_start_day,
    )


@router.get("/cashflow-by-month", response_model=list[MonthlyCashflowDTO])
async def cashflow_by_month(
    account_id: int,
    months: int = Query(default=12, ge=1, le=60),
    budget_start_day: Optional[int] = Query(default=None, ge=1, le=28),
    user_id: int = Depends(get_current_user_id),
    service: AnalyticsQueryService = Depends(get_query_service),
) -> list[MonthlyCashflowDTO]:
    return await service.cashflow_by_month(
        user_id=user_id,
        account_id=account_id,
        months=months,
        budget_start_day=budget_start_day,
    )


@router.get("/comparison", response_model=MonthComparisonDTO)
async def month_comparison(
    account_id: int,
    year: int,
    month: int,
    budget_start_day: Optional[int] = Query(default=None, ge=1, le=28),
    user_id: int = Depends(get_current_user_id),
    service: AnalyticsQueryService = Depends(get_query_service),
) -> MonthComparisonDTO:
    return await service.month_comparison(
        user_id=user_id,
        account_id=account_id,
        year=year,
        month=month,
        budget_start_day=budget_start_day,
    )


@router.get("/transactions", response_model=TransactionSearchResultDTO)
async def transactions(
    account_id: int,
    search: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    category_id: Optional[int] = None,
    tx_type: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user_id: int = Depends(get_current_user_id),
    service: AnalyticsQueryService = Depends(get_query_service),
) -> TransactionSearchResultDTO:
    return await service.search_transactions(
        user_id=user_id,
        account_id=account_id,
        search=search,
        start_date=start_date,
        end_date=end_date,
        category_id=category_id,
        tx_type=tx_type,
        limit=limit,
        offset=offset,
    )


@router.get("/top-merchants", response_model=list[TopMerchantDTO])
async def top_merchants(
    account_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    limit: int = Query(default=10, ge=1, le=100),
    user_id: int = Depends(get_current_user_id),
    service: AnalyticsQueryService = Depends(get_query_service),
) -> list[TopMerchantDTO]:
    return await service.top_merchants(
        user_id=user_id,
        account_id=account_id,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )
