from __future__ import annotations

from contracts.events.account import (
    AccountCreatedEvent,
    AccountCreationFailedEvent,
)
from contracts.events.category import (
    CategoryCreatedEvent,
    CategoryDeletedEvent,
    CategoryUpdatedEvent,
)
from contracts.events.goal import (
    GoalCreatedEvent,
    GoalDeletedEvent,
    GoalUpdatedEvent,
)
from contracts.events.transaction import (
    TransactionCategorizedEvent,
    TransactionCreatedEvent,
    TransactionDeletedEvent,
    TransactionUpdatedEvent,
)
from contracts.events.user import UserCreatedEvent

__all__ = [
    "AccountCreatedEvent",
    "AccountCreationFailedEvent",
    "CategoryCreatedEvent",
    "CategoryDeletedEvent",
    "CategoryUpdatedEvent",
    "GoalCreatedEvent",
    "GoalDeletedEvent",
    "GoalUpdatedEvent",
    "TransactionCategorizedEvent",
    "TransactionCreatedEvent",
    "TransactionDeletedEvent",
    "TransactionUpdatedEvent",
    "UserCreatedEvent",
]
