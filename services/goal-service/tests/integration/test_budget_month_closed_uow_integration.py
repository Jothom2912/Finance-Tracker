from __future__ import annotations

from decimal import Decimal

import pytest
from app.adapters.outbound.unit_of_work import SQLAlchemyBudgetMonthClosedUnitOfWork
from app.application.budget_month_closed_handler import BudgetMonthClosedHandler
from app.database import Base
from app.models import GoalAllocationHistoryModel, GoalModel, UnallocatedBudgetSurplusModel
from contracts.events.budget import BudgetMonthClosedEvent
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool


@pytest.fixture()
async def session_factory() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        yield factory
    finally:
        await engine.dispose()


def _event(surplus_amount: str = "800.00") -> BudgetMonthClosedEvent:
    return BudgetMonthClosedEvent(
        account_id=42,
        year=2026,
        month=4,
        budgeted_amount="5000.00",
        actual_spent="4200.00",
        surplus_amount=surplus_amount,
        correlation_id="12345678-1234-5678-1234-567812345678",
    )


async def _insert_goal(
    session: AsyncSession,
    *,
    goal_id: int = 10,
    account_id: int = 42,
    target_amount: str = "5000.00",
    current_amount: str = "1000.00",
    is_default: bool = True,
) -> None:
    session.add(
        GoalModel(
            idGoal=goal_id,
            name=f"Goal {goal_id}",
            target_amount=Decimal(target_amount),
            current_amount=Decimal(current_amount),
            Account_idAccount=account_id,
            is_default_savings_goal=is_default,
        )
    )
    await session.commit()


@pytest.mark.asyncio()
async def test_handler_allocates_surplus_with_sqlalchemy_uow(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        await _insert_goal(session)
        event = _event()

        result = await BudgetMonthClosedHandler(SQLAlchemyBudgetMonthClosedUnitOfWork(session)).handle(event)

        assert result.status == "allocated"

        goal = await session.get(GoalModel, 10)
        assert goal is not None
        assert goal.current_amount == Decimal("1800.00")

        allocation_result = await session.execute(select(GoalAllocationHistoryModel))
        allocation = allocation_result.scalar_one()
        assert allocation.source_key == event.source_key
        assert allocation.goal_id == 10
        assert allocation.account_id == 42
        assert allocation.amount == Decimal("800.00")
        assert allocation.correlation_id == "12345678-1234-5678-1234-567812345678"


@pytest.mark.asyncio()
async def test_handler_records_unallocated_when_no_default_goal(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        event = _event()

        result = await BudgetMonthClosedHandler(SQLAlchemyBudgetMonthClosedUnitOfWork(session)).handle(event)

        assert result.status == "unallocated_no_default_goal"

        unallocated_result = await session.execute(select(UnallocatedBudgetSurplusModel))
        unallocated = unallocated_result.scalar_one()
        assert unallocated.source_key == event.source_key
        assert unallocated.account_id == 42
        assert unallocated.amount == Decimal("800.00")
        assert unallocated.reason == "no_default_goal"


@pytest.mark.asyncio()
async def test_duplicate_event_does_not_increment_again(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        await _insert_goal(session)
        handler = BudgetMonthClosedHandler(SQLAlchemyBudgetMonthClosedUnitOfWork(session))
        event = _event()

        first_result = await handler.handle(event)
        duplicate_result = await handler.handle(event)

        assert first_result.status == "allocated"
        assert duplicate_result.status == "duplicate"

        goal = await session.get(GoalModel, 10)
        assert goal is not None
        assert goal.current_amount == Decimal("1800.00")

        allocation_result = await session.execute(select(GoalAllocationHistoryModel))
        assert len(allocation_result.scalars().all()) == 1


@pytest.mark.asyncio()
async def test_handler_rolls_back_allocation_when_goal_update_fails(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        await _insert_goal(session)
        event = _event()

        uow = SQLAlchemyBudgetMonthClosedUnitOfWork(session)

        async def failing_increment_current_amount(goal_id: int, amount: Decimal) -> None:
            raise RuntimeError("forced goal update failure")

        uow.goals.increment_current_amount = failing_increment_current_amount  # type: ignore[method-assign]

        with pytest.raises(RuntimeError, match="forced goal update failure"):
            await BudgetMonthClosedHandler(uow).handle(event)

        allocation_result = await session.execute(select(GoalAllocationHistoryModel))
        assert allocation_result.scalars().all() == []

        goal = await session.get(GoalModel, 10)
        assert goal is not None
        assert goal.current_amount == Decimal("1000.00")
