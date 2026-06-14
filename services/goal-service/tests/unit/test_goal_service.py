from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.application.dto import GoalBase, GoalCreate
from app.application.service import GoalService
from app.domain.entities import Goal, GoalStatus
from app.domain.exceptions import AccountNotFoundForGoal, NotAccountOwner

OWNER_USER_ID = 1
OTHER_USER_ID = 99


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
    port.get_owner_user_id.return_value = OWNER_USER_ID
    return port


@pytest.fixture()
def uow() -> MagicMock:
    return make_uow()


@pytest.fixture()
def service(uow: MagicMock, account_port: AsyncMock) -> GoalService:
    return GoalService(uow=uow, account_port=account_port)


def _active_goal(**overrides) -> Goal:
    defaults = dict(
        id=10,
        name="Vacation",
        target_amount=5000,
        current_amount=1000,
        target_date=None,
        status="active",
        account_id=1,
    )
    defaults.update(overrides)
    return Goal(**defaults)


# --- Create ---


@pytest.mark.asyncio()
async def test_create_goal_persists_goal_and_outbox(service: GoalService, uow: MagicMock) -> None:
    uow.goals.create.return_value = _active_goal()

    result = await service.create_goal(
        GoalCreate(
            name="Vacation",
            target_amount=5000,
            current_amount=1000,
            target_date=None,
            status="active",
            Account_idAccount=1,
        ),
        user_id=OWNER_USER_ID,
    )

    assert result.idGoal == 10
    uow.goals.create.assert_awaited_once()
    uow.outbox.add.assert_awaited_once()
    uow.commit.assert_awaited_once()


@pytest.mark.asyncio()
async def test_create_goal_rejects_unknown_account(
    service: GoalService, account_port: AsyncMock, uow: MagicMock
) -> None:
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
            ),
            user_id=OWNER_USER_ID,
        )

    uow.goals.create.assert_not_called()
    uow.outbox.add.assert_not_called()


@pytest.mark.asyncio()
async def test_create_goal_rejects_non_owner(
    service: GoalService,
    uow: MagicMock,
) -> None:
    with pytest.raises(NotAccountOwner):
        await service.create_goal(
            GoalCreate(
                name="Vacation",
                target_amount=5000,
                current_amount=1000,
                target_date=None,
                status="active",
                Account_idAccount=1,
            ),
            user_id=OTHER_USER_ID,
        )

    uow.goals.create.assert_not_called()


# --- Get ---


@pytest.mark.asyncio()
async def test_get_goal_returns_none_for_non_owner(
    service: GoalService,
    uow: MagicMock,
) -> None:
    uow.goals.get_by_id.return_value = _active_goal()

    result = await service.get_goal(10, user_id=OTHER_USER_ID)

    assert result is None


@pytest.mark.asyncio()
async def test_get_goal_returns_dto_for_owner(
    service: GoalService,
    uow: MagicMock,
) -> None:
    uow.goals.get_by_id.return_value = _active_goal()

    result = await service.get_goal(10, user_id=OWNER_USER_ID)

    assert result is not None
    assert result.idGoal == 10


# --- Update ---


@pytest.mark.asyncio()
async def test_update_goal_returns_none_when_missing(service: GoalService, uow: MagicMock) -> None:
    uow.goals.get_by_id.return_value = None

    result = await service.update_goal(
        123,
        GoalBase(name="Updated", target_amount=8000, current_amount=1000, target_date=None, status="active"),
        user_id=OWNER_USER_ID,
    )

    assert result is None
    uow.goals.update.assert_not_called()
    uow.outbox.add.assert_not_called()


@pytest.mark.asyncio()
async def test_update_goal_returns_none_for_non_owner(
    service: GoalService,
    uow: MagicMock,
) -> None:
    uow.goals.get_by_id.return_value = _active_goal()

    result = await service.update_goal(
        10,
        GoalBase(name="Updated", target_amount=8000, current_amount=1000, target_date=None, status="active"),
        user_id=OTHER_USER_ID,
    )

    assert result is None
    uow.goals.update.assert_not_called()


# --- Delete ---


@pytest.mark.asyncio()
async def test_delete_goal_persists_outbox_when_found(service: GoalService, uow: MagicMock) -> None:
    uow.goals.get_by_id.return_value = _active_goal()
    uow.goals.delete.return_value = True

    result = await service.delete_goal(10, user_id=OWNER_USER_ID)

    assert result is True
    uow.goals.delete.assert_awaited_once_with(10)
    uow.outbox.add.assert_awaited_once()
    uow.commit.assert_awaited_once()


@pytest.mark.asyncio()
async def test_delete_goal_returns_false_for_non_owner(
    service: GoalService,
    uow: MagicMock,
) -> None:
    uow.goals.get_by_id.return_value = _active_goal()

    result = await service.delete_goal(10, user_id=OTHER_USER_ID)

    assert result is False
    uow.goals.delete.assert_not_called()


# --- List ---


@pytest.mark.asyncio()
async def test_list_goals_returns_goals_for_owner(
    service: GoalService,
    uow: MagicMock,
) -> None:
    uow.goals.get_all.return_value = [_active_goal(), _active_goal(id=11, name="Car")]

    result = await service.list_goals(account_id=1, user_id=OWNER_USER_ID)

    assert len(result) == 2
    uow.goals.get_all.assert_awaited_once_with(account_id=1)


@pytest.mark.asyncio()
async def test_list_goals_rejects_non_owner(
    service: GoalService,
    uow: MagicMock,
) -> None:
    with pytest.raises(NotAccountOwner):
        await service.list_goals(account_id=1, user_id=OTHER_USER_ID)

    uow.goals.get_all.assert_not_called()


# --- effective_status in DTO ---


@pytest.mark.asyncio()
async def test_dto_includes_effective_status_completed(
    service: GoalService,
    uow: MagicMock,
) -> None:
    uow.goals.get_by_id.return_value = _active_goal(
        target_amount=1000,
        current_amount=1000,
    )

    result = await service.get_goal(10, user_id=OWNER_USER_ID)

    assert result is not None
    assert result.status == GoalStatus.ACTIVE
    assert result.effective_status == GoalStatus.COMPLETED


@pytest.mark.asyncio()
async def test_dto_includes_effective_status_expired(
    service: GoalService,
    uow: MagicMock,
) -> None:
    uow.goals.get_by_id.return_value = _active_goal(
        target_date=date.today() - timedelta(days=1),
    )

    result = await service.get_goal(10, user_id=OWNER_USER_ID)

    assert result is not None
    assert result.status == GoalStatus.ACTIVE
    assert result.effective_status == GoalStatus.EXPIRED


@pytest.mark.asyncio()
async def test_dto_includes_progress_percent(
    service: GoalService,
    uow: MagicMock,
) -> None:
    uow.goals.get_by_id.return_value = _active_goal(
        target_amount=200,
        current_amount=50,
    )

    result = await service.get_goal(10, user_id=OWNER_USER_ID)

    assert result is not None
    assert result.progress_percent == 25.0
