"""
Application service for Budget bounded context.
Orchestrates use cases using domain entities and ports.
"""
import logging
from datetime import date
from typing import Optional

from backend.budget.application.dto import (
    BudgetCreateDTO,
    BudgetResponseDTO,
    BudgetUpdateDTO,
)
from backend.budget.application.ports.inbound import IBudgetService
from backend.budget.application.ports.outbound import IBudgetRepository, ICategoryPort
from backend.budget.domain.entities import Budget
from backend.budget.domain.exceptions import (
    AccountRequiredForBudget,
    CategoryNotFoundForBudget,
    CategoryRequiredForBudget,
)

logger = logging.getLogger(__name__)


class BudgetService(IBudgetService):
    """
    Application service implementing budget use cases.

    Uses constructor injection for all dependencies.
    """

    def __init__(
        self,
        budget_repo: IBudgetRepository,
        category_port: ICategoryPort,
    ):
        self._budget_repo = budget_repo
        self._category_port = category_port

    # ------------------------------------------------------------------
    # Query use cases
    # ------------------------------------------------------------------

    def get_budget(self, budget_id: int) -> Optional[BudgetResponseDTO]:
        budget = self._budget_repo.get_by_id(budget_id)
        if not budget:
            return None
        return self._to_dto(budget)

    def list_budgets(self, account_id: int) -> list[BudgetResponseDTO]:
        budgets = self._budget_repo.get_all(account_id=account_id)
        return [self._to_dto(b) for b in budgets]

    # ------------------------------------------------------------------
    # Command use cases
    # ------------------------------------------------------------------

    def create_budget(self, dto: BudgetCreateDTO) -> BudgetResponseDTO:
        if not dto.Account_idAccount:
            raise AccountRequiredForBudget()

        category_id = dto.category_id
        if not category_id:
            raise CategoryRequiredForBudget()

        if not self._category_port.exists(category_id):
            raise CategoryNotFoundForBudget(category_id)

        # Build budget date from month/year if provided, otherwise use dto.budget_date
        budget_date = dto.budget_date
        if dto.month and dto.year:
            try:
                budget_date = date(int(dto.year), int(dto.month), 1)
            except (ValueError, TypeError):
                pass

        budget = Budget(
            id=None,
            amount=dto.amount,
            budget_date=budget_date,
            account_id=dto.Account_idAccount,
            category_id=category_id,
        )

        created = self._budget_repo.create(budget)
        logger.debug("Budget %s oprettet", created.id)
        return self._to_dto(created)

    def update_budget(
        self, budget_id: int, dto: BudgetUpdateDTO
    ) -> Optional[BudgetResponseDTO]:
        existing = self._budget_repo.get_by_id(budget_id)
        if not existing:
            return None

        update_data = dto.model_dump(exclude_unset=True)

        # Resolve budget_date from month/year or from direct field
        budget_date = existing.budget_date
        if "month" in update_data or "year" in update_data:
            month = update_data.pop("month", None)
            year = update_data.pop("year", None)
            if month and year:
                try:
                    budget_date = date(int(year), int(month), 1)
                except (ValueError, TypeError):
                    pass
        elif "budget_date" in update_data and update_data["budget_date"] is not None:
            budget_date = update_data["budget_date"]

        # Resolve category_id
        category_id = update_data.pop("category_id", None)
        if category_id is not None:
            if not self._category_port.exists(category_id):
                raise CategoryNotFoundForBudget(category_id)
        else:
            category_id = existing.category_id

        updated = Budget(
            id=budget_id,
            amount=update_data.get("amount", existing.amount),
            budget_date=budget_date,
            account_id=update_data.get("Account_idAccount", existing.account_id),
            category_id=category_id,
        )

        result = self._budget_repo.update(updated)
        return self._to_dto(result)

    def delete_budget(self, budget_id: int) -> bool:
        return self._budget_repo.delete(budget_id)

    # ------------------------------------------------------------------
    # Mapping helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_dto(budget: Budget) -> BudgetResponseDTO:
        return BudgetResponseDTO(
            idBudget=budget.id,
            amount=budget.amount,
            budget_date=budget.budget_date,
            Account_idAccount=budget.account_id,
        )
