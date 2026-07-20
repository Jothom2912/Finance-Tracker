from __future__ import annotations

from datetime import date

from contracts.base import BaseEvent


class GoalCreatedEvent(BaseEvent):
    event_type: str = "goal.created"
    event_version: int = 1
    goal_id: int
    user_id: int
    name: str | None = None
    target_amount: str
    current_amount: str
    target_date: date | None = None
    status: str | None = None


class GoalUpdatedEvent(BaseEvent):
    event_type: str = "goal.updated"
    event_version: int = 1
    goal_id: int
    user_id: int
    name: str | None = None
    target_amount: str
    current_amount: str
    target_date: date | None = None
    status: str | None = None


class GoalDeletedEvent(BaseEvent):
    event_type: str = "goal.deleted"
    event_version: int = 1
    goal_id: int
    user_id: int


class GoalReachedEvent(BaseEvent):
    """Published by goal-service when a **surplus allocation** brings a goal to
    or over its target (the automatic ADR-0003 path — F1-08).

    Carries ``account_id`` rather than ``user_id`` on purpose: the allocation
    runs account-scoped and must not depend on account-service to emit. The
    consumer (notification-service) resolves the owner itself, so a down
    account-service delays the notification (retry/DLQ) without ever failing
    the money movement.

    The manual goal-edit path emits ``goal.updated`` instead; both dedupe on
    ``goal.reached:{goal_id}`` downstream, so a goal never notifies twice.
    """

    event_type: str = "goal.reached"
    event_version: int = 1
    goal_id: int
    account_id: int
    name: str | None = None
    target_amount: str
    current_amount: str
