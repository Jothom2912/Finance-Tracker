"""Legacy-implementering af IFinancialAnalyticsPort.

Tynd wrapper om den eksisterende in-process aggregering
(AnalyticsService + HttpAnalyticsReadRepository) — nul adfærdsændring.
Beholdes én release efter cutover til analytics-service, derefter
slettes den sammen med gatewayens aggregeringskode (ADR-004).
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from app.application.dto import FinancialOverview, MonthlyExpenses, TransactionProjection
from app.application.ports.outbound import IFinancialAnalyticsPort
from app.application.service import AnalyticsService


class LegacyFinancialAnalyticsAdapter(IFinancialAnalyticsPort):
    def __init__(self, analytics_service: AnalyticsService) -> None:
        self._service = analytics_service

    def get_financial_overview(
        self,
        account_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> FinancialOverview:
        return self._service.get_financial_overview(account_id=account_id, start_date=start_date, end_date=end_date)

    def get_expenses_by_month(
        self,
        account_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        budget_start_day: int = 1,
    ) -> list[MonthlyExpenses]:
        rows = self._service.get_expenses_by_month(
            account_id=account_id,
            start_date=start_date,
            end_date=end_date,
            budget_start_day=budget_start_day,
        )
        return [MonthlyExpenses(**row) for row in rows]

    def list_transactions(
        self,
        account_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        category_id: Optional[int] = None,
        tx_type: Optional[str] = None,
        limit: int = 100,
    ) -> list[TransactionProjection]:
        return self._service.list_transaction_projections(
            account_id=account_id,
            start_date=start_date,
            end_date=end_date,
            category_id=category_id,
            tx_type=tx_type,
            limit=limit,
        )
