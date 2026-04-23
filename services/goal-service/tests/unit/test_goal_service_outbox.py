from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.dto import GoalBase, GoalCreate
from app.application.service import GoalService
from app.domain.entities import Goal


def _make_uow() -> MagicMock:
    uow = MagicMock()
    uow.goals = AsyncMock()
    uow.outbox = AsyncMock()
    uow.commit = AsyncMock()
    uow.rollback = AsyncMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=False)
    return uow


@pytest.fixture()
def uow() -> MagicMock:
    return _make_uow()


@pytest.fixture()
def account_port() -> AsyncMock:
    port = AsyncMock()
    port.exists.return_value = True
    return port


@pytest.fixture()
def service(uow: MagicMock, account_port: AsyncMock) -> GoalService:
    return GoalService(uow=uow, account_port=account_port)


@pytest.mark.asyncio()
async def test_create_goal_writes_outbox(service: GoalService, uow: MagicMock) -> None:
    uow.goals.create.return_value = Goal(
        id=10,
        name="Vacation",
        target_amount=5000,
        current_amount=1000,
        target_date=None,
        status="active",
        account_id=1,
    )

    dto = GoalCreate(
        name="Vacation",
        target_amount=5000,
        current_amount=1000,
        target_date=None,
        status="active",
        Account_idAccount=1,
    )

    result = await service.create_goal(dto)

    assert result.idGoal == 10
    uow.outbox.add.assert_awaited_once()
    call = uow.outbox.add.call_args.kwargs
    assert call["aggregate_type"] == "goal"
    assert call["aggregate_id"] == "10"
    assert call["event"].event_type == "goal.created"
    uow.commit.assert_awaited_once()


@pytest.mark.asyncio()
async def test_update_goal_writes_outbox(service: GoalService, uow: MagicMock) -> None:
    existing = Goal(
        id=10,
        name="Vacation",
        target_amount=5000,
        current_amount=1000,
        target_date=None,
        status="active",
        account_id=1,
    )
    updated = Goal(
        id=10,
        name="Vacation 2",
        target_amount=6000,
        current_amount=1200,
        target_date=None,
        status="active",
        account_id=1,
    )
    uow.goals.get_by_id.return_value = existing
    uow.goals.update.return_value = updated

    dto = GoalBase(
        name="Vacation 2",
        target_amount=6000,
        current_amount=1200,
        target_date=None,
        status="active",
    )

    result = await service.update_goal(10, dto)

    assert result is not None
    assert result.idGoal == 10
    call = uow.outbox.add.call_args.kwargs
    assert call["event"].event_type == "goal.updated"
    uow.commit.assert_awaited_once()


@pytest.mark.asyncio()
async def test_delete_goal_writes_outbox(service: GoalService, uow: MagicMock) -> None:
    existing = Goal(
        id=10,
        name="Vacation",
        target_amount=5000,
        current_amount=1000,
        target_date=None,
        status="active",
        account_id=1,
    )
    uow.goals.get_by_id.return_value = existing
    uow.goals.delete.return_value = True

    result = await service.delete_goal(10)

    assert result is True
    call = uow.outbox.add.call_args.kwargs
    assert call["event"].event_type == "goal.deleted"
    assert call["aggregate_id"] == "10"
    uow.commit.assert_awaited_once()
