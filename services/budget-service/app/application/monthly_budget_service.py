from __future__ import annotations

import logging
from decimal import Decimal
from typing import Optional

from contracts.events.budget import (
    BudgetMonthClosedEvent,
    make_budget_month_closed_source_key,
)

from app.application.dto import (
    BudgetLineResponse,
    CopyBudgetRequest,
    MonthlyBudgetCreate,
    MonthlyBudgetResponse,
    MonthlyBudgetSummary,
    MonthlyBudgetSummaryItem,
    MonthlyBudgetUpdate,
)
from app.application.ports.outbound import (
    ICategoryPort,
    ITransactionPort,
    IUnitOfWork,
)
from app.domain.budget_period import budget_period
from app.domain.entities import BudgetLine, MonthlyBudget
from app.domain.exceptions import (
    AccountRequiredForMonthlyBudget,
    CategoryNotFoundForBudgetLine,
    MonthlyBudgetAlreadyClosed,
    MonthlyBudgetAlreadyExists,
    MonthlyBudgetNotFound,
    NoBudgetToCopy,
    UpstreamServiceUnavailable,
)

logger = logging.getLogger(__name__)


class MonthlyBudgetService:
    def __init__(
        self,
        uow: IUnitOfWork,
        transaction_port: ITransactionPort,
        category_port: ICategoryPort,
    ) -> None:
        self._uow = uow
        self._transaction_port = transaction_port
        self._category_port = category_port

    # -- Queries ---------------------------------------------------------------

    async def get_or_none(
        self,
        account_id: int,
        month: int,
        year: int,
        user_id: int,
    ) -> Optional[MonthlyBudgetResponse]:
        budget = await self._uow.monthly_budgets.get_by_account_and_period(
            account_id,
            month,
            year,
            user_id,
        )
        if not budget:
            return None
        return await self._to_response(budget)

    async def get_summary(
        self,
        account_id: int,
        month: int,
        year: int,
        budget_start_day: int = 1,
        user_id: int = 0,
    ) -> MonthlyBudgetSummary:
        if not account_id:
            raise AccountRequiredForMonthlyBudget()

        budget = await self._uow.monthly_budgets.get_by_account_and_period(
            account_id,
            month,
            year,
            user_id,
        )
        start_date, end_date = budget_period(year, month, budget_start_day)
        try:
            expenses = await self._transaction_port.get_expenses_by_category(
                account_id,
                start_date,
                end_date,
                user_id=user_id,
            )
        except UpstreamServiceUnavailable:
            # Read-only summary degraderer gracefully når transaction-service er
            # nede (viser spent=0) — bevarer tidligere fail-open adfærd her.
            # close_month må derimod ALDRIG fail-open (se close_month).
            expenses = {}
        category_names = await self._category_port.get_all_names()

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
                        category_name=category_names.get(line.category_id, "Ukendt"),
                        budget_amount=round(line.amount, 2),
                        spent_amount=round(spent, 2),
                        remaining_amount=round(remaining, 2),
                        percentage_used=round(pct, 2),
                    ),
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
                ),
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

    # -- Commands --------------------------------------------------------------

    async def create(
        self,
        account_id: int,
        user_id: int,
        dto: MonthlyBudgetCreate,
    ) -> MonthlyBudgetResponse:
        if not account_id:
            raise AccountRequiredForMonthlyBudget()

        existing = await self._uow.monthly_budgets.get_by_account_and_period(
            account_id,
            dto.month,
            dto.year,
            user_id,
        )
        if existing:
            raise MonthlyBudgetAlreadyExists(dto.month, dto.year)

        await self._validate_categories([line.category_id for line in dto.lines])

        budget = MonthlyBudget(
            id=None,
            month=dto.month,
            year=dto.year,
            account_id=account_id,
            user_id=user_id,
            lines=[BudgetLine(id=None, category_id=l.category_id, amount=l.amount) for l in dto.lines],
        )

        created = await self._uow.monthly_budgets.create(budget)
        await self._uow.commit()
        logger.debug("MonthlyBudget %s created for %02d/%d", created.id, dto.month, dto.year)
        return await self._to_response(created)

    async def update(
        self,
        budget_id: int,
        account_id: int,
        user_id: int,
        dto: MonthlyBudgetUpdate,
    ) -> MonthlyBudgetResponse:
        existing = await self._uow.monthly_budgets.get_by_id_for_account(budget_id, account_id, user_id)
        if not existing:
            raise MonthlyBudgetNotFound(budget_id)

        await self._validate_categories([line.category_id for line in dto.lines])

        existing.lines = [BudgetLine(id=None, category_id=l.category_id, amount=l.amount) for l in dto.lines]

        updated = await self._uow.monthly_budgets.update(existing)
        await self._uow.commit()
        return await self._to_response(updated)

    async def delete(self, budget_id: int, account_id: int, user_id: int) -> bool:
        result = await self._uow.monthly_budgets.delete(budget_id, account_id, user_id)
        await self._uow.commit()
        return result

    async def copy_to_month(
        self,
        account_id: int,
        user_id: int,
        dto: CopyBudgetRequest,
    ) -> MonthlyBudgetResponse:
        if not account_id:
            raise AccountRequiredForMonthlyBudget()

        source = await self._uow.monthly_budgets.get_by_account_and_period(
            account_id,
            dto.source_month,
            dto.source_year,
            user_id,
        )
        if not source or not source.lines:
            raise NoBudgetToCopy(dto.source_month, dto.source_year)

        existing_target = await self._uow.monthly_budgets.get_by_account_and_period(
            account_id,
            dto.target_month,
            dto.target_year,
            user_id,
        )
        if existing_target:
            raise MonthlyBudgetAlreadyExists(dto.target_month, dto.target_year)

        new_budget = MonthlyBudget(
            id=None,
            month=dto.target_month,
            year=dto.target_year,
            account_id=account_id,
            user_id=user_id,
            lines=[BudgetLine(id=None, category_id=l.category_id, amount=l.amount) for l in source.lines],
        )

        created = await self._uow.monthly_budgets.create(new_budget)
        await self._uow.commit()
        logger.debug(
            "Copied budget from %02d/%d to %02d/%d",
            dto.source_month,
            dto.source_year,
            dto.target_month,
            dto.target_year,
        )
        return await self._to_response(created)

    async def close_month(
        self,
        account_id: int,
        year: int,
        month: int,
        budget_start_day: int = 1,
        user_id: int = 0,
    ) -> None:
        # --- Reads + HTTP call — outside the write transaction ----------------
        budget = await self._uow.monthly_budgets.get_by_account_and_period(
            account_id,
            month,
            year,
            user_id,
        )
        if not budget:
            raise MonthlyBudgetNotFound(month=month, year=year)

        start_date, end_date = budget_period(year, month, budget_start_day)
        # Fail-closed: kan udgifterne ikke hentes, propagerer
        # UpstreamServiceUnavailable — måneden lukkes IKKE og der udsendes
        # ingen event (spent=0 ville kreditere et fiktivt overskud til mål).
        expenses = await self._transaction_port.get_expenses_by_category(
            account_id,
            start_date,
            end_date,
            user_id=user_id,
        )

        budgeted = Decimal(str(budget.total_budget))
        spent = sum(Decimal(str(v)) for v in expenses.values())
        surplus = max(Decimal(0), budgeted - spent)

        source_key = make_budget_month_closed_source_key(account_id, year, month)
        event = BudgetMonthClosedEvent(
            account_id=account_id,
            year=year,
            month=month,
            budgeted_amount=str(budgeted),
            actual_spent=str(spent),
            surplus_amount=str(surplus),
            correlation_id=source_key,
        )

        # --- Atomic write: closed_at + outbox in one commit -------------------
        closed = await self._uow.monthly_budgets.mark_closed(budget.id)
        if not closed:
            raise MonthlyBudgetAlreadyClosed(month, year)

        await self._uow.outbox.add(event, "monthly_budget", str(budget.id))
        await self._uow.commit()

        logger.info(
            "Month %02d/%d closed for account %s — surplus %s",
            month,
            year,
            account_id,
            surplus,
        )

    # -- Helpers ---------------------------------------------------------------

    async def _validate_categories(self, category_ids: list[int]) -> None:
        for cat_id in category_ids:
            if not await self._category_port.exists(cat_id):
                raise CategoryNotFoundForBudgetLine(cat_id)

    async def _to_response(self, budget: MonthlyBudget) -> MonthlyBudgetResponse:
        category_names = await self._category_port.get_all_names()
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
