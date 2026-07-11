from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.application.dto import FinancialOverview, MonthlyExpenses, TransactionProjection


class IFinancialAnalyticsPort(ABC):
    """Grov, præ-aggregeret read-side port.

    Erstatter IAnalyticsReadRepository som resolvers afhængighed:
    aggregering hører hjemme bag porten (ES-aggs i analytics-service),
    ikke i gatewayen. Implementeringer: legacy-adapter (in-process
    aggregering, transition), analytics-service HTTP-klient, og
    dual-read wrapperen der sammenligner de to.
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


class IAnalyticsReadRepository(ABC):
    @abstractmethod
    def get_transactions(
        self,
        account_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> list[dict]:
        pass


class ICategoryReadRepository(ABC):
    """Taxonomy read source — categorization-service per ADR-003."""

    @abstractmethod
    def get_categories(self) -> list[dict]:
        pass

    @abstractmethod
    def get_subcategories(self) -> list[dict]:
        pass
