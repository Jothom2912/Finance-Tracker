from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from app.application.dto import BudgetCreateDTO, BudgetResponseDTO, BudgetUpdateDTO
from app.application.ports.inbound import IBudgetService
from app.application.ports.outbound import IBudgetRepository, ICategoryPort
from app.domain.entities import Budget
from app.domain.exceptions import (
    AccountRequiredForBudget,
    CategoryNotFoundForBudget,
    CategoryRequiredForBudget,
)

logger = logging.getLogger(__name__)


class BudgetService(IBudgetService):

    def __init__(self, repo: IBudgetRepository, category_port: ICategoryPort):
        self._repo = repo
        self._category_port = category_port

    async def get_budget(self, budget_id: int, user_id: int) -> Optional[BudgetResponseDTO]:
        budget = await self._repo.get_by_id(budget_id)
        return self._to_dto(budget) if budget else None

    async def list_budgets(self, account_id: int) -> list[BudgetResponseDTO]:
        budgets = await self._repo.get_all(account_id=account_id)
        return [self._to_dto(b) for b in budgets]

    async def create_budget(self, user_id: int, dto: BudgetCreateDTO) -> BudgetResponseDTO:
        if not dto.account_id:
            raise AccountRequiredForBudget()
        if not dto.category_id:
            raise CategoryRequiredForBudget()
        if not await self._category_port.exists(dto.category_id):
            raise CategoryNotFoundForBudget(dto.category_id)

        budget_date = dto.budget_date
        if dto.month and dto.year:
            budget_date = date(int(dto.year), int(dto.month), 1)

        budget = Budget(
            id=None,
            amount=dto.amount,
            budget_date=budget_date,
            account_id=dto.account_id,
            category_id=dto.category_id,
        )
        created = await self._repo.create(budget)
        logger.debug("Budget %s oprettet", created.id)
        return self._to_dto(created)

    async def update_budget(self, budget_id: int, dto: BudgetUpdateDTO) -> Optional[BudgetResponseDTO]:
        existing = await self._repo.get_by_id(budget_id)
        if not existing:
            return None

        budget_date = existing.budget_date
        if dto.month and dto.year:
            budget_date = date(int(dto.year), int(dto.month), 1)
        elif dto.budget_date:
            budget_date = dto.budget_date

        category_id = existing.category_id
        if dto.category_id is not None:
            if not await self._category_port.exists(dto.category_id):
                raise CategoryNotFoundForBudget(dto.category_id)
            category_id = dto.category_id

        updated = Budget(
            id=budget_id,
            amount=dto.amount if dto.amount is not None else existing.amount,
            budget_date=budget_date,
            account_id=existing.account_id,
            category_id=category_id,
        )
        result = await self._repo.update(updated)
        return self._to_dto(result)

    async def delete_budget(self, budget_id: int) -> bool:
        return await self._repo.delete(budget_id)

    @staticmethod
    def _to_dto(budget: Budget) -> BudgetResponseDTO:
        return BudgetResponseDTO(
            id=budget.id,
            amount=budget.amount,
            budget_date=budget.budget_date,
            account_id=budget.account_id,
            category_id=budget.category_id,
        )