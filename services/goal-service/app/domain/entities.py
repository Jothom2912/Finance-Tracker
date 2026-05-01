from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass
class Goal:
    id: int | None
    name: str | None
    target_amount: float
    current_amount: float
    target_date: date | None
    status: str | None
    account_id: int


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
