from __future__ import annotations

import pytest
from app.application.service import NotificationService
from app.workers.notification_consumer import ROUTING_KEYS, NotificationConsumer
from contracts.events.bank import BankSyncCompletedEvent
from contracts.events.budget import BudgetLineThresholdCrossedEvent
from contracts.events.goal import GoalReachedEvent, GoalUpdatedEvent
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


async def test_dispatch_routes_goal_updated_and_filters_below_target() -> None:
    payload = GoalUpdatedEvent(
        goal_id=1, user_id=7, target_amount="1000", current_amount="10", status="active"
    ).model_dump(mode="json")

    result = await _consumer()._dispatch(_service(), "goal.updated", payload, "cid")
    assert result.status == "ignored_not_reached"


async def test_dispatch_routes_goal_reached() -> None:
    payload = GoalReachedEvent(
        goal_id=9, account_id=5, name="Ferie", target_amount="1000", current_amount="1000"
    ).model_dump(mode="json")

    result = await _consumer()._dispatch(_service(), "goal.reached", payload, "cid")
    assert result.status == "created"
    assert result.source_key == "goal.reached:9"


async def test_dispatch_routes_budget_threshold() -> None:
    payload = BudgetLineThresholdCrossedEvent(
        account_id=5,
        year=2026,
        month=6,
        category_id=3,
        category_name="Dagligvarer",
        budgeted_amount="1000.00",
        spent_amount="850.00",
        percentage_used=85,
        threshold=80,
        days_remaining=12,
    ).model_dump(mode="json")

    result = await _consumer()._dispatch(_service(), "budget.line_threshold_crossed", payload, "cid")
    assert result.status == "created"
    assert result.source_key == "budget.line_threshold_crossed:5:2026:6:3:80"


def test_budget_threshold_routing_key_is_bound() -> None:
    assert "budget.line_threshold_crossed" in ROUTING_KEYS


async def test_unexpected_event_type_is_poison() -> None:
    with pytest.raises(PoisonMessageError):
        await _consumer()._dispatch(_service(), "transaction.created", {}, "cid")


async def test_malformed_payload_is_poison() -> None:
    with pytest.raises(PoisonMessageError):
        # missing all required fields for the declared type
        await _consumer()._dispatch(_service(), "bank.sync.completed", {"event_type": "x"}, "cid")
