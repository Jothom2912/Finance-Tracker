from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

import pytest
from app.application.budget_month_closed_handler import BudgetMonthClosedHandler
from app.domain.entities import Goal
from contracts.events.budget import BudgetMonthClosedEvent


@dataclass
class AllocationRecord:
    source_key: str
    goal_id: int
    account_id: int
    amount: Decimal
    correlation_id: str | None


@dataclass
class UnallocatedRecord:
    source_key: str
    account_id: int
    amount: Decimal
    reason: Literal["no_default_goal", "goal_already_complete"]
    correlation_id: str | None


@dataclass
class _CommittedState:
    goals: dict[int, Goal]
    allocations: dict[tuple[str, int], AllocationRecord]
    unallocated: dict[str, UnallocatedRecord]


class FakeGoalSavingsRepository:
    def __init__(self, uow: FakeBudgetMonthClosedUnitOfWork) -> None:
        self._uow = uow

    async def get_default_savings_goal(self, account_id: int) -> Goal | None:
        for goal in self._uow.staged.goals.values():
            if goal.account_id == account_id:
                return goal
        return None

    async def increment_current_amount(self, goal_id: int, amount: Decimal) -> None:
        if self._uow.fail_on_increment:
            raise RuntimeError("forced increment failure")

        goal = self._uow.staged.goals[goal_id]
        self._uow.staged.goals[goal_id] = Goal(
            id=goal.id,
            name=goal.name,
            target_amount=goal.target_amount,
            current_amount=Decimal(str(goal.current_amount)) + amount,
            target_date=goal.target_date,
            status=goal.status,
            account_id=goal.account_id,
        )


class FakeGoalAllocationRepository:
    def __init__(self, uow: FakeBudgetMonthClosedUnitOfWork) -> None:
        self._uow = uow

    async def source_key_exists(self, source_key: str) -> bool:
        return any(key[0] == source_key for key in self._uow.staged.allocations)

    async def add_allocation(
        self,
        *,
        source_key: str,
        goal_id: int,
        account_id: int,
        amount: Decimal,
        correlation_id: str | None,
    ) -> None:
        self._uow.staged.allocations[(source_key, goal_id)] = AllocationRecord(
            source_key=source_key,
            goal_id=goal_id,
            account_id=account_id,
            amount=amount,
            correlation_id=correlation_id,
        )


class FakeUnallocatedBudgetSurplusRepository:
    def __init__(self, uow: FakeBudgetMonthClosedUnitOfWork) -> None:
        self._uow = uow

    async def source_key_exists(self, source_key: str) -> bool:
        return source_key in self._uow.staged.unallocated

    async def add_unallocated(
        self,
        *,
        source_key: str,
        account_id: int,
        amount: Decimal,
        reason: Literal["no_default_goal", "goal_already_complete"],
        correlation_id: str | None,
    ) -> None:
        self._uow.staged.unallocated[source_key] = UnallocatedRecord(
            source_key=source_key,
            account_id=account_id,
            amount=amount,
            reason=reason,
            correlation_id=correlation_id,
        )


class FakeBudgetMonthClosedUnitOfWork:
    def __init__(self, goals: list[Goal] | None = None) -> None:
        self.committed = _CommittedState(
            goals={goal.id: goal for goal in goals or [] if goal.id is not None},
            allocations={},
            unallocated={},
        )
        self.staged = deepcopy(self.committed)
        self.fail_on_increment = False
        self.goals = FakeGoalSavingsRepository(self)
        self.allocations = FakeGoalAllocationRepository(self)
        self.unallocated = FakeUnallocatedBudgetSurplusRepository(self)

    async def __aenter__(self) -> FakeBudgetMonthClosedUnitOfWork:
        self.staged = deepcopy(self.committed)
        return self

    async def __aexit__(self, exc_type, _exc_val, _exc_tb) -> None:
        if exc_type:
            await self.rollback()

    async def commit(self) -> None:
        self.committed = deepcopy(self.staged)

    async def rollback(self) -> None:
        self.staged = deepcopy(self.committed)


def _event(surplus_amount: str = "800.00") -> BudgetMonthClosedEvent:
    return BudgetMonthClosedEvent(
        account_id=42,
        year=2026,
        month=4,
        budgeted_amount="5000.00",
        actual_spent="4200.00",
        surplus_amount=surplus_amount,
        correlation_id="test-correlation-id",
    )


def _goal(
    *,
    goal_id: int = 10,
    account_id: int = 42,
    target_amount: Decimal = Decimal("5000.00"),
    current_amount: Decimal = Decimal("1000.00"),
) -> Goal:
    return Goal(
        id=goal_id,
        name="Vacation",
        target_amount=target_amount,
        current_amount=current_amount,
        target_date=None,
        status="active",
        account_id=account_id,
    )


@pytest.mark.asyncio()
async def test_zero_surplus_is_ignored_without_opening_transaction() -> None:
    uow = FakeBudgetMonthClosedUnitOfWork(goals=[_goal()])
    result = await BudgetMonthClosedHandler(uow).handle(_event(surplus_amount="0.00"))

    assert result.status == "ignored_zero_surplus"
    assert result.amount == Decimal("0.00")
    assert result.goal_id is None
    assert uow.committed.allocations == {}
    assert uow.committed.unallocated == {}


@pytest.mark.asyncio()
async def test_no_default_goal_records_unallocated_surplus() -> None:
    uow = FakeBudgetMonthClosedUnitOfWork()
    event = _event()

    result = await BudgetMonthClosedHandler(uow).handle(event)

    assert result.status == "unallocated_no_default_goal"
    assert result.source_key == event.source_key
    assert result.amount == Decimal("800.00")
    assert result.goal_id is None

    record = uow.committed.unallocated[event.source_key]
    assert record.reason == "no_default_goal"
    assert record.amount == Decimal("800.00")


@pytest.mark.asyncio()
async def test_complete_default_goal_records_unallocated_surplus() -> None:
    uow = FakeBudgetMonthClosedUnitOfWork(
        goals=[_goal(target_amount=Decimal("5000.00"), current_amount=Decimal("5000.00"))]
    )
    event = _event()

    result = await BudgetMonthClosedHandler(uow).handle(event)

    assert result.status == "unallocated_goal_already_complete"
    assert result.goal_id == 10

    record = uow.committed.unallocated[event.source_key]
    assert record.reason == "goal_already_complete"
    assert record.amount == Decimal("800.00")


@pytest.mark.asyncio()
async def test_surplus_allocates_to_default_goal() -> None:
    uow = FakeBudgetMonthClosedUnitOfWork(goals=[_goal()])
    event = _event()

    result = await BudgetMonthClosedHandler(uow).handle(event)

    assert result.status == "allocated"
    assert result.goal_id == 10
    assert result.amount == Decimal("800.00")

    allocation = uow.committed.allocations[(event.source_key, 10)]
    goal = uow.committed.goals[10]
    assert allocation.amount == Decimal("800.00")
    assert goal.current_amount == Decimal("1800.00")


@pytest.mark.asyncio()
async def test_duplicate_event_returns_success_without_double_increment() -> None:
    uow = FakeBudgetMonthClosedUnitOfWork(goals=[_goal()])
    handler = BudgetMonthClosedHandler(uow)
    event = _event()

    first_result = await handler.handle(event)
    duplicate_result = await handler.handle(event)

    assert first_result.status == "allocated"
    assert duplicate_result.status == "duplicate"
    assert duplicate_result.amount == Decimal("800.00")
    assert uow.committed.goals[10].current_amount == Decimal("1800.00")
    assert len(uow.committed.allocations) == 1


@pytest.mark.asyncio()
async def test_insert_and_update_are_rolled_back_together_when_update_fails() -> None:
    uow = FakeBudgetMonthClosedUnitOfWork(goals=[_goal()])
    uow.fail_on_increment = True
    event = _event()

    with pytest.raises(RuntimeError, match="forced increment failure"):
        await BudgetMonthClosedHandler(uow).handle(event)

    assert uow.committed.allocations == {}
    assert uow.committed.goals[10].current_amount == Decimal("1000.00")
