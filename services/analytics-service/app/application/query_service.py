"""Query-use-cases: validering, dato-defaults og delegation til query-porten.

Default-vinduerne replikerer gatewayens AnalyticsService (overview:
sidste 30 dage; expenses-by-month: 12 måneder tilbage fra d. 1.) så
dual-read kan sammenligne output direkte. Ingen ``date.today()`` i
domænelogik — clock injiceres (deterministiske tests, jf. konventioner).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta
from typing import Optional

from app.application.dto import (
    FinancialOverviewDTO,
    HybridSearchResultDTO,
    MonthComparisonDTO,
    MonthlyCashflowDTO,
    MonthlyExpensesDTO,
    TopMerchantDTO,
    TransactionSearchResultDTO,
)
from app.application.ports.outbound import IAnalyticsQueryPort
from app.domain.budget_period import budget_period, determine_budget_month
from app.domain.exceptions import InvalidPeriodError
from app.shared.logging import execute_with_logging

DEFAULT_BUDGET_START_DAY = 1


class AnalyticsQueryService:
    def __init__(
        self,
        query_port: IAnalyticsQueryPort,
        clock: Callable[[], date] = date.today,
    ) -> None:
        self._port = query_port
        self._clock = clock

    async def _resolve_budget_start_day(self, user_id: int, account_id: int, budget_start_day: Optional[int]) -> int:
        if budget_start_day is not None:
            return budget_start_day
        stored = await self._port.get_budget_start_day(user_id=user_id, account_id=account_id)
        return stored if stored is not None else DEFAULT_BUDGET_START_DAY

    @execute_with_logging("analytics.financial_overview")
    async def financial_overview(
        self,
        *,
        user_id: int,
        account_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> FinancialOverviewDTO:
        end_date = end_date or self._clock()
        start_date = start_date or end_date - timedelta(days=30)
        if start_date > end_date:
            raise InvalidPeriodError()
        return await self._port.financial_overview(
            user_id=user_id, account_id=account_id, start_date=start_date, end_date=end_date
        )

    @execute_with_logging("analytics.expenses_by_month")
    async def expenses_by_month(
        self,
        *,
        user_id: int,
        account_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        budget_start_day: Optional[int] = None,
    ) -> list[MonthlyExpensesDTO]:
        end_date = end_date or self._clock()
        start_date = start_date or date(end_date.year - 1, end_date.month, 1)
        if start_date > end_date:
            raise InvalidPeriodError()
        start_day = await self._resolve_budget_start_day(user_id, account_id, budget_start_day)
        return await self._port.expenses_by_month(
            user_id=user_id,
            account_id=account_id,
            start_date=start_date,
            end_date=end_date,
            budget_start_day=start_day,
        )

    @execute_with_logging("analytics.cashflow_by_month")
    async def cashflow_by_month(
        self,
        *,
        user_id: int,
        account_id: int,
        months: int = 12,
        budget_start_day: Optional[int] = None,
    ) -> list[MonthlyCashflowDTO]:
        if months < 1:
            raise InvalidPeriodError("Antal måneder skal være mindst 1.")
        start_day = await self._resolve_budget_start_day(user_id, account_id, budget_start_day)

        # Vinduet slutter ved den NUVÆRENDE budgetmåneds slutning og går
        # `months` budgetmåneder tilbage — dense/zero-filled i storen.
        today = self._clock()
        current_year, current_month = determine_budget_month(today, start_day)
        _, end_date = budget_period(current_year, current_month, start_day)

        first_year, first_month = current_year, current_month
        for _ in range(months - 1):
            if first_month == 1:
                first_year, first_month = first_year - 1, 12
            else:
                first_month -= 1
        start_date, _ = budget_period(first_year, first_month, start_day)

        return await self._port.cashflow_by_month(
            user_id=user_id,
            account_id=account_id,
            start_date=start_date,
            end_date=end_date,
            budget_start_day=start_day,
        )

    @execute_with_logging("analytics.month_comparison")
    async def month_comparison(
        self,
        *,
        user_id: int,
        account_id: int,
        year: int,
        month: int,
        budget_start_day: Optional[int] = None,
    ) -> MonthComparisonDTO:
        if not 1 <= month <= 12:
            raise InvalidPeriodError("Måned skal være mellem 1 og 12.")
        start_day = await self._resolve_budget_start_day(user_id, account_id, budget_start_day)
        return await self._port.month_comparison(
            user_id=user_id,
            account_id=account_id,
            year=year,
            month=month,
            budget_start_day=start_day,
        )

    @execute_with_logging("analytics.search_transactions")
    async def search_transactions(
        self,
        *,
        user_id: int,
        account_id: int,
        search: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        category_id: Optional[int] = None,
        tx_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        sort: str = "date_desc",
    ) -> TransactionSearchResultDTO:
        if start_date and end_date and start_date > end_date:
            raise InvalidPeriodError()
        return await self._port.search_transactions(
            user_id=user_id,
            account_id=account_id,
            search=search,
            start_date=start_date,
            end_date=end_date,
            category_id=category_id,
            tx_type=tx_type,
            limit=limit,
            offset=offset,
            sort=sort,
        )

    @execute_with_logging("analytics.hybrid_search")
    async def hybrid_search_transactions(
        self,
        *,
        user_id: int,
        query: str,
        query_vector: Optional[list[float]] = None,
        account_id: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        category_id: Optional[int] = None,
        subcategory_id: Optional[int] = None,
        category_name: Optional[str] = None,
        tx_type: Optional[str] = None,
        amount_min: Optional[float] = None,
        amount_max: Optional[float] = None,
        limit: int = 10,
    ) -> HybridSearchResultDTO:
        if start_date and end_date and start_date > end_date:
            raise InvalidPeriodError()
        return await self._port.hybrid_search_transactions(
            user_id=user_id,
            query=query,
            query_vector=query_vector,
            account_id=account_id,
            start_date=start_date,
            end_date=end_date,
            category_id=category_id,
            subcategory_id=subcategory_id,
            category_name=category_name,
            tx_type=tx_type,
            amount_min=amount_min,
            amount_max=amount_max,
            limit=limit,
        )

    @execute_with_logging("analytics.top_merchants")
    async def top_merchants(
        self,
        *,
        user_id: int,
        account_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 10,
    ) -> list[TopMerchantDTO]:
        end_date = end_date or self._clock()
        start_date = start_date or end_date - timedelta(days=30)
        if start_date > end_date:
            raise InvalidPeriodError()
        return await self._port.top_merchants(
            user_id=user_id,
            account_id=account_id,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )
