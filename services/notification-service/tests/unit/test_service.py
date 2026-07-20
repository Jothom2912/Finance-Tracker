from __future__ import annotations

import pytest
from app.application.service import NotificationService
from app.domain.exceptions import AccountNotFound, AccountOwnerUnavailable
from contracts.events.bank import BankSyncCompletedEvent
from contracts.events.budget import BudgetMonthClosedEvent
from contracts.events.goal import GoalUpdatedEvent

from tests._fakes import FakeAccountOwner, FakeEmail, FakeUoW


def _service(uow: FakeUoW, email: FakeEmail, owner: FakeAccountOwner) -> NotificationService:
    return NotificationService(uow, email, owner)  # type: ignore[arg-type]


def _bank_event() -> BankSyncCompletedEvent:
    return BankSyncCompletedEvent(
        connection_id="c1",
        account_id=1,
        user_id=7,
        total_fetched=3,
        new_imported=3,
        duplicates_skipped=0,
        errors=0,
    )


async def test_bank_sync_creates_notification_and_sends_email() -> None:
    uow, email, owner = FakeUoW(), FakeEmail(), FakeAccountOwner(user_id=7)
    result = await _service(uow, email, owner).handle_bank_sync_completed(_bank_event())

    assert result.status == "created"
    assert result.source_key.startswith("bank.sync.completed:c1:")
    assert uow.committed is True
    assert len(uow.notifications.rows) == 1
    assert uow.notifications.rows[0].user_id == 7
    assert email.sent == [(7, "Banksynkronisering færdig")]


async def test_redelivery_of_same_event_is_deduplicated() -> None:
    uow, email, owner = FakeUoW(), FakeEmail(), FakeAccountOwner(user_id=7)
    service = _service(uow, email, owner)
    event = _bank_event()  # same correlation_id both times

    first = await service.handle_bank_sync_completed(event)
    second = await service.handle_bank_sync_completed(event)

    assert first.status == "created"
    assert second.status == "duplicate"
    assert len(uow.notifications.rows) == 1
    assert len(email.sent) == 1  # no second email


async def test_goal_updated_ignored_when_not_completed() -> None:
    uow, email, owner = FakeUoW(), FakeEmail(), FakeAccountOwner(user_id=7)
    event = GoalUpdatedEvent(goal_id=1, user_id=7, target_amount="1000", current_amount="500", status="active")
    result = await _service(uow, email, owner).handle_goal_updated(event)

    assert result.status == "ignored_not_completed"
    assert uow.notifications.rows == []
    assert email.sent == []


async def test_goal_reached_creates_once_per_goal() -> None:
    uow, email, owner = FakeUoW(), FakeEmail(), FakeAccountOwner(user_id=7)
    service = _service(uow, email, owner)
    completed = GoalUpdatedEvent(
        goal_id=42,
        user_id=7,
        target_amount="1000",
        current_amount="1000",
        status="completed",
        name="Ferie",
    )

    first = await service.handle_goal_updated(completed)
    # a later goal.updated (still completed) must not notify again
    second = await service.handle_goal_updated(completed)

    assert first.status == "created"
    assert first.source_key == "goal.reached:42"
    assert second.status == "duplicate"
    assert len(uow.notifications.rows) == 1


def _month_event() -> BudgetMonthClosedEvent:
    return BudgetMonthClosedEvent(
        account_id=5,
        year=2026,
        month=6,
        budgeted_amount="1000",
        actual_spent="800",
        surplus_amount="200",
    )


async def test_month_closed_resolves_owner_and_creates() -> None:
    uow, email, owner = FakeUoW(), FakeEmail(), FakeAccountOwner(user_id=99)
    result = await _service(uow, email, owner).handle_budget_month_closed(_month_event())

    assert result.status == "created"
    assert result.source_key == "budget.month_closed:5:2026:6"
    assert uow.notifications.rows[0].user_id == 99


async def test_month_closed_dropped_when_account_missing() -> None:
    uow, email = FakeUoW(), FakeEmail()
    owner = FakeAccountOwner(exc=AccountNotFound(5))
    result = await _service(uow, email, owner).handle_budget_month_closed(_month_event())

    assert result.status == "account_not_found"
    assert uow.notifications.rows == []


async def test_month_closed_propagates_when_account_service_unavailable() -> None:
    uow, email = FakeUoW(), FakeEmail()
    owner = FakeAccountOwner(exc=AccountOwnerUnavailable())
    with pytest.raises(AccountOwnerUnavailable):
        await _service(uow, email, owner).handle_budget_month_closed(_month_event())
    assert uow.notifications.rows == []


async def test_email_failure_does_not_fail_the_notification() -> None:
    uow, email, owner = FakeUoW(), FakeEmail(fail=True), FakeAccountOwner(user_id=7)
    result = await _service(uow, email, owner).handle_bank_sync_completed(_bank_event())

    assert result.status == "created"
    assert len(uow.notifications.rows) == 1
