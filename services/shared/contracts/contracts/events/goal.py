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
