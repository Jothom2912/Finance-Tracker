from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Optional, Self

from contracts.base import BaseEvent

from app.domain.entities import Budget, MonthlyBudget


class IBudgetRepository(ABC):
    @abstractmethod
    async def get_by_id(self, budget_id: int) -> Optional[Budget]: ...

    @abstractmethod
    async def get_all(self, account_id: int, user_id: int) -> list[Budget]: ...

    @abstractmethod
    async def create(self, budget: Budget) -> Budget: ...

    @abstractmethod
    async def update(self, budget: Budget) -> Budget: ...

    @abstractmethod
    async def delete(self, budget_id: int) -> bool: ...


class ICategoryPort(ABC):
    @abstractmethod
    async def exists(self, category_id: int) -> bool: ...

    @abstractmethod
    async def get_name(self, category_id: int) -> Optional[str]: ...

    @abstractmethod
    async def get_all_names(self) -> dict[int, str]: ...


class IMonthlyBudgetRepository(ABC):
    @abstractmethod
    async def get_by_id_for_account(self, budget_id: int, account_id: int, user_id: int) -> Optional[MonthlyBudget]: ...

    @abstractmethod
    async def get_by_account_and_period(
        self,
        account_id: int,
        month: int,
        year: int,
        user_id: int,
    ) -> Optional[MonthlyBudget]: ...

    @abstractmethod
    async def create(self, budget: MonthlyBudget) -> MonthlyBudget: ...

    @abstractmethod
    async def update(self, budget: MonthlyBudget) -> MonthlyBudget: ...

    @abstractmethod
    async def delete(self, budget_id: int, account_id: int, user_id: int) -> bool: ...

    @abstractmethod
    async def list_open_before_period(self, year: int, month: int) -> list[MonthlyBudget]:
        """All budgets with closed_at IS NULL and (year, month) strictly before
        the given period — the scheduled-close sweep candidates (F1-07).
        Not user-scoped: the scheduler closes each row as its stored user_id.
        """
        ...

    @abstractmethod
    async def list_open_for_period(self, year: int, month: int) -> list[MonthlyBudget]:
        """All open budgets FOR the given (still-running) period — the mid-month
        alert sweep candidates (F2-03). Not user-scoped: the scheduler evaluates
        each row as its stored user_id.
        """
        ...

    @abstractmethod
    async def mark_closed(self, budget_id: int) -> bool:
        """Atomic conditional UPDATE: SET closed_at WHERE closed_at IS NULL.

        Returns True if the row was updated (budget closed now),
        False if already closed (rowcount 0). The caller must NOT
        read is_closed first — this method IS the guard.
        """
        ...


class ITransactionPort(ABC):
    @abstractmethod
    async def get_expenses_by_category(
        self,
        account_id: int,
        start_date: date,
        end_date: date,
        user_id: int = 0,
    ) -> dict[int, float]:
        """Raises UpstreamServiceUnavailable hvis transaction-service ikke kan nås."""
        ...


class IOutboxRepository(ABC):
    @abstractmethod
    async def add(self, event: BaseEvent, aggregate_type: str, aggregate_id: str) -> None: ...


class IUnitOfWork(ABC):
    """Repos share one DB session; flush() in repos, commit() here."""

    monthly_budgets: IMonthlyBudgetRepository
    outbox: IOutboxRepository

    @abstractmethod
    async def __aenter__(self) -> Self: ...

    @abstractmethod
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None: ...

    @abstractmethod
    async def commit(self) -> None: ...

    @abstractmethod
    async def rollback(self) -> None: ...
