"""
Application service for MonthlyBudget bounded context.
Orchestrates use cases using domain entities and ports.
"""
from __future__ import annotations

import logging
from typing import Optional

from backend.monthly_budget.application.dto import (
    BudgetLineResponse,
    CopyBudgetRequest,
    MonthlyBudgetCreate,
    MonthlyBudgetResponse,
    MonthlyBudgetSummary,
    MonthlyBudgetSummaryItem,
    MonthlyBudgetUpdate,
)
from backend.monthly_budget.application.ports.inbound import IMonthlyBudgetService
from backend.monthly_budget.application.ports.outbound import (
    ICategoryPort,
    IMonthlyBudgetRepository,
    ITransactionPort,
)
from backend.monthly_budget.domain.entities import BudgetLine, MonthlyBudget
from backend.monthly_budget.domain.exceptions import (
    AccountRequiredForMonthlyBudget,
    CategoryNotFoundForBudgetLine,
    MonthlyBudgetAlreadyExists,
    MonthlyBudgetNotFound,
    NoBudgetToCopy,
)

logger = logging.getLogger(__name__)


class MonthlyBudgetService(IMonthlyBudgetService):
    """Application service implementing monthly budget use cases."""

    def __init__(
        self,
        budget_repo: IMonthlyBudgetRepository,
        transaction_port: ITransactionPort,
        category_port: ICategoryPort,
    ):
        self._budget_repo = budget_repo
        self._transaction_port = transaction_port
        self._category_port = category_port

    # ── Queries ──────────────────────────────────────────────────

    def get_or_none(
        self, account_id: int, month: int, year: int
    ) -> Optional[MonthlyBudgetResponse]:
        budget = self._budget_repo.get_by_account_and_period(account_id, month, year)
        if not budget:
            return None
        return self._to_response(budget)

    def get_summary(
        self, account_id: int, month: int, year: int
    ) -> MonthlyBudgetSummary:
        if not account_id:
            raise AccountRequiredForMonthlyBudget()

        budget = self._budget_repo.get_by_account_and_period(account_id, month, year)
        expenses = self._transaction_port.get_expenses_by_category(
            account_id, month, year
        )
        category_names = self._category_port.get_all_names()

        items: list[MonthlyBudgetSummaryItem] = []
        total_budget = 0.0
        total_spent = 0.0
        over_budget_count = 0
        budgeted_category_ids: set[int] = set()

        if budget:
            for line in budget.lines:
                spent = expenses.get(line.category_id, 0.0)
                remaining = line.amount - spent
                pct = (spent / line.amount * 100.0) if line.amount > 0 else 0.0

                if remaining < 0:
                    over_budget_count += 1

                items.append(
                    MonthlyBudgetSummaryItem(
                        category_id=line.category_id,
                        category_name=category_names.get(
                            line.category_id, "Ukendt"
                        ),
                        budget_amount=round(line.amount, 2),
                        spent_amount=round(spent, 2),
                        remaining_amount=round(remaining, 2),
                        percentage_used=round(pct, 2),
                    )
                )
                total_budget += line.amount
                total_spent += spent
                budgeted_category_ids.add(line.category_id)

        for cat_id, spent in expenses.items():
            if cat_id in budgeted_category_ids:
                continue
            over_budget_count += 1
            items.append(
                MonthlyBudgetSummaryItem(
                    category_id=cat_id,
                    category_name=category_names.get(cat_id, "Ukendt"),
                    budget_amount=0.0,
                    spent_amount=round(spent, 2),
                    remaining_amount=round(-spent, 2),
                    percentage_used=100.0,
                )
            )
            total_spent += spent

        return MonthlyBudgetSummary(
            month=month,
            year=year,
            budget_id=budget.id if budget else None,
            items=items,
            total_budget=round(total_budget, 2),
            total_spent=round(total_spent, 2),
            total_remaining=round(total_budget - total_spent, 2),
            over_budget_count=over_budget_count,
        )

    # ── Commands ─────────────────────────────────────────────────

    def create(
        self, account_id: int, dto: MonthlyBudgetCreate
    ) -> MonthlyBudgetResponse:
        if not account_id:
            raise AccountRequiredForMonthlyBudget()

        existing = self._budget_repo.get_by_account_and_period(
            account_id, dto.month, dto.year
        )
        if existing:
            raise MonthlyBudgetAlreadyExists(dto.month, dto.year)

        self._validate_categories([line.category_id for line in dto.lines])

        budget = MonthlyBudget(
            id=None,
            month=dto.month,
            year=dto.year,
            account_id=account_id,
            lines=[
                BudgetLine(id=None, category_id=l.category_id, amount=l.amount)
                for l in dto.lines
            ],
        )

        created = self._budget_repo.create(budget)
        logger.debug("MonthlyBudget %s created for %02d/%d", created.id, dto.month, dto.year)
        return self._to_response(created)

    def update(
        self, budget_id: int, account_id: int, dto: MonthlyBudgetUpdate
    ) -> MonthlyBudgetResponse:
        existing = self._budget_repo.get_by_id_for_account(budget_id, account_id)
        if not existing:
            raise MonthlyBudgetNotFound(budget_id)

        self._validate_categories([line.category_id for line in dto.lines])

        existing.lines = [
            BudgetLine(id=None, category_id=l.category_id, amount=l.amount)
            for l in dto.lines
        ]

        updated = self._budget_repo.update(existing)
        return self._to_response(updated)

    def delete(self, budget_id: int, account_id: int) -> bool:
        return self._budget_repo.delete(budget_id, account_id)

    def copy_to_month(
        self, account_id: int, dto: CopyBudgetRequest
    ) -> MonthlyBudgetResponse:
        if not account_id:
            raise AccountRequiredForMonthlyBudget()

        source = self._budget_repo.get_by_account_and_period(
            account_id, dto.source_month, dto.source_year
        )
        if not source or not source.lines:
            raise NoBudgetToCopy(dto.source_month, dto.source_year)

        existing_target = self._budget_repo.get_by_account_and_period(
            account_id, dto.target_month, dto.target_year
        )
        if existing_target:
            raise MonthlyBudgetAlreadyExists(dto.target_month, dto.target_year)

        new_budget = MonthlyBudget(
            id=None,
            month=dto.target_month,
            year=dto.target_year,
            account_id=account_id,
            lines=[
                BudgetLine(id=None, category_id=l.category_id, amount=l.amount)
                for l in source.lines
            ],
        )

        created = self._budget_repo.create(new_budget)
        logger.debug(
            "Copied budget from %02d/%d to %02d/%d",
            dto.source_month, dto.source_year,
            dto.target_month, dto.target_year,
        )
        return self._to_response(created)

    # ── Helpers ───────────────────────────────────────────────────

    def _validate_categories(self, category_ids: list[int]) -> None:
        for cat_id in category_ids:
            if not self._category_port.exists(cat_id):
                raise CategoryNotFoundForBudgetLine(cat_id)

    def _to_response(self, budget: MonthlyBudget) -> MonthlyBudgetResponse:
        category_names = self._category_port.get_all_names()
        return MonthlyBudgetResponse(
            id=budget.id,
            month=budget.month,
            year=budget.year,
            total_budget=round(budget.total_budget, 2),
            created_at=budget.created_at,
            lines=[
                BudgetLineResponse(
                    id=line.id or 0,
                    category_id=line.category_id,
                    category_name=category_names.get(line.category_id),
                    amount=round(line.amount, 2),
                )
                for line in budget.lines
            ],
        )
