from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from app.domain.entities import Budget


class IBudgetRepository(ABC):

    @abstractmethod
    async def get_by_id(self, budget_id: int) -> Optional[Budget]: ...

    @abstractmethod
    async def get_all(self, account_id: int) -> list[Budget]: ...

    @abstractmethod
    async def create(self, budget: Budget) -> Budget: ...

    @abstractmethod
    async def update(self, budget: Budget) -> Budget: ...

    @abstractmethod
    async def delete(self, budget_id: int) -> bool: ...


class ICategoryPort(ABC):

    @abstractmethod
    async def exists(self, category_id: int) -> bool: ...
