from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.application.dto import (
        FinancialOverview,
        MonthComparison,
        MonthlyCashflow,
        MonthlyExpenses,
        TransactionProjection,
    )


class IFinancialAnalyticsPort(ABC):
    """Grov, præ-aggregeret read-side port.

    Aggregering hører hjemme bag porten (ES-aggs i analytics-service),
    ikke i gatewayen. Implementering: analytics-service HTTP-klienten
    (legacy in-process-aggregering + dual-read blev slettet efter
    ADR-0004-cutoveren).
    """

    @abstractmethod
    def get_financial_overview(
        self,
        account_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> FinancialOverview:
        pass

    @abstractmethod
    def get_expenses_by_month(
        self,
        account_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        budget_start_day: int = 1,
    ) -> list[MonthlyExpenses]:
        pass

    @abstractmethod
    def list_transactions(
        self,
        account_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        category_id: Optional[int] = None,
        tx_type: Optional[str] = None,
        limit: int = 100,
    ) -> list[TransactionProjection]:
        pass


class IAnalyticsInsightsPort(ABC):
    """Analytics-only læsekapabiliteter (kræver ES-read-siden, ADR-0004).

    Holdes adskilt fra IFinancialAnalyticsPort så resolvers erklærer
    præcist hvilken kapabilitet de bruger — cashflow, sammenligning og
    dansk fuldtekstsøgning findes kun i analytics-service.
    """

    @abstractmethod
    def get_cashflow_by_month(
        self,
        account_id: int,
        months: int = 12,
        budget_start_day: int = 1,
    ) -> list[MonthlyCashflow]:
        pass

    @abstractmethod
    def get_month_comparison(
        self,
        account_id: int,
        year: int,
        month: int,
        budget_start_day: int = 1,
    ) -> MonthComparison:
        pass

    @abstractmethod
    def search_transactions(
        self,
        account_id: int,
        query: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        category_id: Optional[int] = None,
        tx_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[int, list[TransactionProjection]]:
        """Returnerer (total_count, side af resultater)."""


class ICategoryReadRepository(ABC):
    """Taxonomy read source — categorization-service per ADR-003."""

    @abstractmethod
    def get_categories(self) -> list[dict]:
        pass

    @abstractmethod
    def get_subcategories(self) -> list[dict]:
        pass
