from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Optional

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
    async def get_by_id_for_account(self, budget_id: int, account_id: int) -> Optional[MonthlyBudget]: ...

    @abstractmethod
    async def get_by_account_and_period(self, account_id: int, month: int, year: int) -> Optional[MonthlyBudget]: ...

    @abstractmethod
    async def create(self, budget: MonthlyBudget) -> MonthlyBudget: ...

    @abstractmethod
    async def update(self, budget: MonthlyBudget) -> MonthlyBudget: ...

    @abstractmethod
    async def delete(self, budget_id: int, account_id: int) -> bool: ...


class ITransactionPort(ABC):

    @abstractmethod
    async def get_expenses_by_category(
        self, account_id: int, start_date: date, end_date: date,
    ) -> dict[int, float]: ...


class IOutboxRepository(ABC):

    @abstractmethod
    async def add(self, event: object, aggregate_type: str, aggregate_id: str) -> None: ...
