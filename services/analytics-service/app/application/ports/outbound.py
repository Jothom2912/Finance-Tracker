from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Optional

from app.application.dto import (
    FinancialOverviewDTO,
    MonthComparisonDTO,
    MonthlyCashflowDTO,
    MonthlyExpensesDTO,
    TopMerchantDTO,
    TransactionSearchResultDTO,
)

# ── Skriveside (projection stores) ──────────────────────────────────
#
# Alle upserts er idempotente og konvergente: dokument-_id = entity-id,
# og ``event_ts`` (epoch-millis af eventets timestamp) bruges som guard
# så duplikerede/out-of-order events aldrig kan rulle nyere state
# tilbage. Se ADR-004.


class ITransactionProjectionStore(ABC):
    @abstractmethod
    async def upsert_core(
        self,
        *,
        transaction_id: int,
        account_id: int,
        user_id: int,
        amount: float,
        transaction_type: str,
        tx_date: date,
        description: str,
        category_id: Optional[int],
        category_name: Optional[str],
        subcategory_id: Optional[int],
        subcategory_name: Optional[str],
        categorization_tier: Optional[str],
        categorization_confidence: Optional[str],
        event_ts: int,
    ) -> None:
        """Upsert af kernefelter fra transaction.created/updated."""

    @abstractmethod
    async def apply_categorization(
        self,
        *,
        transaction_id: int,
        category_id: int,
        category_name: str,
        subcategory_id: Optional[int],
        subcategory_name: str,
        categorization_tier: str,
        categorization_confidence: str,
        event_ts: int,
    ) -> None:
        """Partiel upsert af kategoriseringsfelter fra transaction.categorized."""

    @abstractmethod
    async def mark_deleted(self, *, transaction_id: int, event_ts: int) -> None:
        """Soft-delete tombstone; terminal (sene replays genopliver aldrig)."""


class IAccountProjectionStore(ABC):
    @abstractmethod
    async def upsert(
        self,
        *,
        account_id: int,
        user_id: int,
        name: str,
        saldo: float,
        budget_start_day: int,
        event_ts: int,
    ) -> None:
        pass


class ITaxonomyProjectionStore(ABC):
    @abstractmethod
    async def upsert_category(
        self,
        *,
        category_id: int,
        name: str,
        category_type: str,
        display_order: int,
        is_deleted: bool,
        event_ts: int,
    ) -> bool:
        """Returnerer True hvis upserten blev anvendt (ikke stale/noop) —
        rename-propagering må kun ske for anvendte opdateringer."""

    @abstractmethod
    async def upsert_subcategory(
        self,
        *,
        subcategory_id: int,
        category_id: int,
        name: str,
        is_default: bool,
        is_deleted: bool,
        event_ts: int,
    ) -> bool:
        pass

    @abstractmethod
    async def get_subcategory_name(self, subcategory_id: int) -> Optional[str]:
        """Navneopslag til core-events, der kun bærer subcategory_id."""

    @abstractmethod
    async def propagate_category_rename(self, *, category_id: int, name: str) -> None:
        """Opdatér denormaliseret category_name på transaktionsdokumenter."""

    @abstractmethod
    async def propagate_subcategory_rename(self, *, subcategory_id: int, name: str) -> None:
        pass


class IGoalProjectionStore(ABC):
    @abstractmethod
    async def upsert(
        self,
        *,
        goal_id: int,
        user_id: int,
        name: Optional[str],
        target_amount: float,
        current_amount: float,
        target_date: Optional[date],
        status: Optional[str],
        is_deleted: bool,
        event_ts: int,
    ) -> None:
        pass

    @abstractmethod
    async def mark_deleted(self, *, goal_id: int, event_ts: int) -> None:
        pass


# ── Læseside (query port) ───────────────────────────────────────────


class IAnalyticsQueryPort(ABC):
    """Aggregerings- og søge-queries mod read-storen.

    Tenant-isolation er kontraktuel: ALLE implementeringer skal filtrere
    på ``user_id`` + ``account_id`` i hvert query.
    """

    @abstractmethod
    async def financial_overview(
        self,
        *,
        user_id: int,
        account_id: int,
        start_date: date,
        end_date: date,
    ) -> FinancialOverviewDTO:
        pass

    @abstractmethod
    async def expenses_by_month(
        self,
        *,
        user_id: int,
        account_id: int,
        start_date: date,
        end_date: date,
        budget_start_day: int,
    ) -> list[MonthlyExpensesDTO]:
        pass

    @abstractmethod
    async def cashflow_by_month(
        self,
        *,
        user_id: int,
        account_id: int,
        start_date: date,
        end_date: date,
        budget_start_day: int,
    ) -> list[MonthlyCashflowDTO]:
        pass

    @abstractmethod
    async def month_comparison(
        self,
        *,
        user_id: int,
        account_id: int,
        year: int,
        month: int,
        budget_start_day: int,
    ) -> MonthComparisonDTO:
        pass

    @abstractmethod
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
        pass

    @abstractmethod
    async def top_merchants(
        self,
        *,
        user_id: int,
        account_id: int,
        start_date: date,
        end_date: date,
        limit: int = 10,
    ) -> list[TopMerchantDTO]:
        pass

    @abstractmethod
    async def get_budget_start_day(self, *, user_id: int, account_id: int) -> Optional[int]:
        """budget_start_day fra accounts-projektionen; None hvis ukendt."""
