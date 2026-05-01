from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from app.application.ports.outbound import IBudgetMonthClosedUnitOfWork
from app.domain.entities import Goal
from contracts.events.budget import BudgetMonthClosedEvent

BudgetMonthClosedHandlingStatus = Literal[
    "ignored_zero_surplus",
    "unallocated_no_default_goal",
    "unallocated_goal_already_complete",
    "allocated",
    "duplicate",
]


@dataclass(frozen=True)
class BudgetMonthClosedHandlingResult:
    """Result of handling a budget month close event.

    ``amount`` is always the parsed ``surplus_amount`` from the event, even
    when the event is a duplicate or no state was persisted.
    """

    status: BudgetMonthClosedHandlingStatus
    source_key: str
    amount: Decimal
    goal_id: int | None = None


class BudgetMonthClosedHandler:
    def __init__(self, uow: IBudgetMonthClosedUnitOfWork) -> None:
        self._uow = uow

    async def handle(self, event: BudgetMonthClosedEvent) -> BudgetMonthClosedHandlingResult:
        amount = Decimal(event.surplus_amount)
        source_key = event.source_key

        if amount == Decimal("0"):
            return BudgetMonthClosedHandlingResult(
                status="ignored_zero_surplus",
                source_key=source_key,
                amount=amount,
            )

        async with self._uow:
            if await self._already_handled(source_key):
                return BudgetMonthClosedHandlingResult(
                    status="duplicate",
                    source_key=source_key,
                    amount=amount,
                )

            goal = await self._uow.goals.get_default_savings_goal(event.account_id)
            if goal is None:
                await self._uow.unallocated.add_unallocated(
                    source_key=source_key,
                    account_id=event.account_id,
                    amount=amount,
                    reason="no_default_goal",
                    correlation_id=event.correlation_id,
                )
                await self._uow.commit()
                return BudgetMonthClosedHandlingResult(
                    status="unallocated_no_default_goal",
                    source_key=source_key,
                    amount=amount,
                )

            if self._is_goal_complete(goal):
                await self._uow.unallocated.add_unallocated(
                    source_key=source_key,
                    account_id=event.account_id,
                    amount=amount,
                    reason="goal_already_complete",
                    correlation_id=event.correlation_id,
                )
                await self._uow.commit()
                return BudgetMonthClosedHandlingResult(
                    status="unallocated_goal_already_complete",
                    source_key=source_key,
                    amount=amount,
                    goal_id=goal.id,
                )

            await self._uow.allocations.add_allocation(
                source_key=source_key,
                goal_id=self._require_goal_id(goal),
                account_id=event.account_id,
                amount=amount,
                correlation_id=event.correlation_id,
            )
            await self._uow.goals.increment_current_amount(
                goal_id=self._require_goal_id(goal),
                amount=amount,
            )
            await self._uow.commit()

            return BudgetMonthClosedHandlingResult(
                status="allocated",
                source_key=source_key,
                amount=amount,
                goal_id=goal.id,
            )

    async def _already_handled(self, source_key: str) -> bool:
        return await self._uow.allocations.source_key_exists(
            source_key
        ) or await self._uow.unallocated.source_key_exists(source_key)

    @staticmethod
    def _is_goal_complete(goal: Goal) -> bool:
        return Decimal(str(goal.current_amount)) >= Decimal(str(goal.target_amount))

    @staticmethod
    def _require_goal_id(goal: Goal) -> int:
        if goal.id is None:
            raise ValueError("Default savings goal must have an id before allocation")
        return goal.id
