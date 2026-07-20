from __future__ import annotations

import pytest
from app.application.service import NotificationService
from app.workers.notification_consumer import NotificationConsumer
from contracts.events.bank import BankSyncCompletedEvent
from contracts.events.goal import GoalUpdatedEvent
from messaging import PoisonMessageError

from tests._fakes import FakeAccountOwner, FakeEmail, FakeUoW


def _service() -> NotificationService:
    return NotificationService(FakeUoW(), FakeEmail(), FakeAccountOwner(user_id=7))


def _consumer() -> NotificationConsumer:
    # Construction only stores config + builds stateless adapters (no I/O).
    return NotificationConsumer()


async def test_dispatch_routes_bank_sync() -> None:
    payload = BankSyncCompletedEvent(
        connection_id="c1",
        account_id=1,
        user_id=7,
        total_fetched=2,
        new_imported=2,
        duplicates_skipped=0,
        errors=0,
    ).model_dump(mode="json")

    result = await _consumer()._dispatch(_service(), "bank.sync.completed", payload, "cid")
    assert result.status == "created"


async def test_dispatch_routes_goal_updated_and_filters_status() -> None:
    payload = GoalUpdatedEvent(
        goal_id=1, user_id=7, target_amount="1000", current_amount="10", status="active"
    ).model_dump(mode="json")

    result = await _consumer()._dispatch(_service(), "goal.updated", payload, "cid")
    assert result.status == "ignored_not_completed"


async def test_unexpected_event_type_is_poison() -> None:
    with pytest.raises(PoisonMessageError):
        await _consumer()._dispatch(_service(), "transaction.created", {}, "cid")


async def test_malformed_payload_is_poison() -> None:
    with pytest.raises(PoisonMessageError):
        # missing all required fields for the declared type
        await _consumer()._dispatch(_service(), "bank.sync.completed", {"event_type": "x"}, "cid")
