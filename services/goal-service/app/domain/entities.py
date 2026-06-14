from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import date, datetime


class GoalStatus(str, enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    EXPIRED = "expired"


@dataclass
class Goal:
    id: int | None
    name: str | None
    target_amount: float
    current_amount: float
    target_date: date | None
    status: str | None
    account_id: int

    @property
    def progress_percent(self) -> float:
        if self.target_amount == 0:
            return 100.0
        return round((self.current_amount / self.target_amount) * 100, 2)

    @property
    def effective_status(self) -> GoalStatus:
        if self.current_amount >= self.target_amount and self.target_amount > 0:
            return GoalStatus.COMPLETED
        if self.target_date is not None and self.target_date < date.today() and self.status != GoalStatus.PAUSED:
            return GoalStatus.EXPIRED
        if self.status == GoalStatus.PAUSED:
            return GoalStatus.PAUSED
        return GoalStatus.ACTIVE


@dataclass
class OutboxEntry:
    id: str
    aggregate_type: str
    aggregate_id: str
    event_type: str
    payload_json: str
    correlation_id: str | None
    status: str
    attempts: int
    next_attempt_at: datetime
    created_at: datetime
