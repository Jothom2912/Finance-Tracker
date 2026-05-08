"""Domain entities for Account bounded context.

Pure domain objects with no infrastructure dependencies."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Account:
    """Account domain entity."""

    id: Optional[int]
    name: str
    saldo: float
    user_id: int
    budget_start_day: int = 1

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Account name is required")
        if not self.user_id:
            raise ValueError("User ID is required")
        self.budget_start_day = max(1, min(28, self.budget_start_day))


@dataclass
class AccountGroupUser:
    """Simplified user representation within account group context."""

    id: int
    username: str


@dataclass
class AccountGroup:
    """Account group domain entity."""

    id: Optional[int]
    name: str
    max_users: int
    users: list[AccountGroupUser]

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Group name is required")
        if self.max_users < 1:
            raise ValueError("Max users must be at least 1")


@dataclass
class OutboxEntry:
    """Outbox event entry for the publisher worker."""

    id: str
    aggregate_type: str
    aggregate_id: str
    event_type: str
    payload_json: str
    correlation_id: Optional[str]
    status: str
    attempts: int
    next_attempt_at: Optional[datetime]
    created_at: Optional[datetime]
