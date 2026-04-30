from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.dto import GoalBase, GoalCreate
from app.application.service import GoalService
from app.domain.entities import Goal
from app.domain.exceptions import AccountNotFoundForGoal


def make_uow() -> MagicMock:
    uow = MagicMock()
    uow.goals = AsyncMock()
    uow.outbox = AsyncMock()
    uow.commit = AsyncMock()
    uow.rollback = AsyncMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=False)
    return uow


@pytest.fixture()
def account_port() -> AsyncMock:
    port = AsyncMock()
    port.exists.return_value = True
    return port


@pytest.fixture()
def uow() -> MagicMock:
    return make_uow()


@pytest.fixture()
def service(uow: MagicMock, account_port: AsyncMock) -> GoalService:
    return GoalService(uow=uow, account_port=account_port)


@pytest.mark.asyncio()
async def test_create_goal_persists_goal_and_outbox(service: GoalService, uow: MagicMock) -> None:
    uow.goals.create.return_value = Goal(
        id=10,
        name="Vacation",
        target_amount=5000,
        current_amount=1000,
        target_date=None,
        status="active",
        account_id=1,
    )

    result = await service.create_goal(
        GoalCreate(
            name="Vacation",
            target_amount=5000,
            current_amount=1000,
            target_date=None,
            status="active",
            Account_idAccount=1,
        )
    )

    assert result.idGoal == 10
    uow.goals.create.assert_awaited_once()
    uow.outbox.add.assert_awaited_once()
    uow.commit.assert_awaited_once()


@pytest.mark.asyncio()
async def test_create_goal_rejects_unknown_account(service: GoalService, account_port: AsyncMock, uow: MagicMock) -> None:
    account_port.exists.return_value = False

    with pytest.raises(AccountNotFoundForGoal):
        await service.create_goal(
            GoalCreate(
                name="Vacation",
                target_amount=5000,
                current_amount=1000,
                target_date=None,
                status="active",
                Account_idAccount=99,
            )
        )

    uow.goals.create.assert_not_called()
    uow.outbox.add.assert_not_called()


@pytest.mark.asyncio()
async def test_update_goal_returns_none_when_missing(service: GoalService, uow: MagicMock) -> None:
    uow.goals.get_by_id.return_value = None

    result = await service.update_goal(
        123,
        GoalBase(
            name="Updated",
            target_amount=8000,
            current_amount=1000,
            target_date=None,
            status="active",
        ),
    )

    assert result is None
    uow.goals.update.assert_not_called()
    uow.outbox.add.assert_not_called()


@pytest.mark.asyncio()
async def test_delete_goal_persists_outbox_when_found(service: GoalService, uow: MagicMock) -> None:
    uow.goals.get_by_id.return_value = Goal(
        id=10,
        name="Vacation",
        target_amount=5000,
        current_amount=1000,
        target_date=None,
        status="active",
        account_id=1,
    )
    uow.goals.delete.return_value = True

    result = await service.delete_goal(10)

    assert result is True
    uow.goals.delete.assert_awaited_once_with(10)
    uow.outbox.add.assert_awaited_once()
    uow.commit.assert_awaited_once()
