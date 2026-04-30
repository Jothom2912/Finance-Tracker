from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from app.application.dto import BudgetCreateDTO, BudgetResponseDTO, BudgetUpdateDTO


class IBudgetService(ABC):

    @abstractmethod
    async def get_budget(self, budget_id: int, user_id: int) -> Optional[BudgetResponseDTO]: ...

    @abstractmethod
    async def list_budgets(self, account_id: int) -> list[BudgetResponseDTO]: ...

    @abstractmethod
    async def create_budget(self, user_id: int, dto: BudgetCreateDTO) -> BudgetResponseDTO: ...

    @abstractmethod
    async def update_budget(self, budget_id: int, dto: BudgetUpdateDTO) -> Optional[BudgetResponseDTO]: ...

    @abstractmethod
    async def delete_budget(self, budget_id: int) -> bool: ...
