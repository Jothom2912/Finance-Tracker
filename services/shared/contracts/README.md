# finans-tracker-contracts

Shared event contracts for async inter-service communication via RabbitMQ.

Services depend on this package for event schemas instead of depending on each other (dependency inversion). The package is **transport-agnostic** and contains only Pydantic data models — no RabbitMQ or messaging dependencies.

## Quick Start

### Install

```bash
uv add --editable services/shared/contracts/
```

### Usage

```python
from contracts import (
    BudgetMonthClosedEvent,
    CategoryCreatedEvent,
    TransactionCreatedEvent,
    UserCreatedEvent,
)

# User events
event = UserCreatedEvent(user_id=42, email="alice@example.com", username="alice")
json_bytes = event.to_json()
restored = UserCreatedEvent.from_json(json_bytes)

# Transaction events (amount as string for decimal precision)
tx_event = TransactionCreatedEvent(
    transaction_id=1,
    user_id=42,
    amount="125.50",
    account_id=1,
    category="Groceries",
    description="Weekly shopping",
)

# Category events
cat_event = CategoryCreatedEvent(
    category_id=1,
    name="Groceries",
    category_type="expense",
)

# Budget close events (surplus as string for decimal precision)
budget_event = BudgetMonthClosedEvent(
    account_id=1,
    year=2026,
    month=4,
    budgeted_amount="5000.00",
    actual_spent="4200.00",
    surplus_amount="800.00",
)
```

## Available Events

### User Events (`contracts.events.user`)

| Event | Routing Key | Fields |
|-------|-------------|--------|
| `UserCreatedEvent` | `user.created` | `user_id`, `email`, `username` |

### Account Events (`contracts.events.account`)

| Event | Routing Key | Fields |
|-------|-------------|--------|
| `AccountCreatedEvent` | `account.created` | `account_id`, `user_id`, `account_name` |
| `AccountCreationFailedEvent` | `account.creation_failed` | `user_id`, `reason` |

### Category Events (`contracts.events.category`)

| Event | Routing Key | Fields |
|-------|-------------|--------|
| `CategoryCreatedEvent` | `category.created` | `category_id`, `name`, `category_type` |
| `CategoryUpdatedEvent` | `category.updated` | `category_id`, `name`, `category_type`, `previous_name`, `previous_type` |
| `CategoryDeletedEvent` | `category.deleted` | `category_id`, `name`, `category_type` |

### Budget Events (`contracts.events.budget`)

| Event | Routing Key | Fields |
|-------|-------------|--------|
| `BudgetMonthClosedEvent` | `budget.month_closed` | `account_id`, `year`, `month`, `budgeted_amount` (str), `actual_spent` (str), `surplus_amount` (str) |

See [ADR-0003](../../../docs/adr/0003-goal-allocation-from-budget-surplus.md#decision) for the event rationale, idempotency key, and consumer semantics.

### Transaction Events (`contracts.events.transaction`)

| Event | Routing Key | Fields |
|-------|-------------|--------|
| `TransactionCreatedEvent` | `transaction.created` | `transaction_id`, `user_id`, `amount` (str), `account_id`, `category`, `description` |
| `TransactionUpdatedEvent` | `transaction.updated` | `transaction_id`, `user_id`, `amount` (str), `previous_amount`, `account_id`, `category`, `previous_category`, `description` |
| `TransactionDeletedEvent` | `transaction.deleted` | `transaction_id`, `user_id`, `amount` (str), `account_id` |

## Adding New Events

1. Create a new file under `contracts/events/` (e.g. `budget.py`).
2. Define one or more event classes inheriting from `BaseEvent`.
3. Re-export the new classes in `contracts/events/__init__.py` and `contracts/__init__.py`.

```python
from __future__ import annotations

from contracts.base import BaseEvent


class BudgetThresholdEvent(BaseEvent):
    event_type: str = "budget.threshold.80pct"
    event_version: int = 1

    budget_id: int
    user_id: int
    spent_percentage: float
```

## Architecture

```text
contracts/
├── base.py            # BaseEvent (immutable Pydantic model)
└── events/
    ├── user.py        # UserCreatedEvent
    ├── account.py     # AccountCreatedEvent, AccountCreationFailedEvent
    ├── budget.py      # BudgetMonthClosedEvent
    ├── category.py    # CategoryCreatedEvent, CategoryUpdatedEvent, CategoryDeletedEvent
    └── transaction.py # TransactionCreatedEvent, TransactionUpdatedEvent, TransactionDeletedEvent
```

Events are **frozen** (immutable value objects) and carry:

| Field | Type | Default |
|-------|------|---------|
| `event_type` | `str` | Set per subclass |
| `event_version` | `int` | `1` |
| `correlation_id` | `str` | Random UUID |
| `timestamp` | `datetime` | Current UTC time |

## Design Decisions

- **Amount as string in money events**: Pydantic can serialize `Decimal` in ways that lose precision or formatting. By sending amounts as strings (e.g. `"125.50"`), consumers can parse them with `Decimal("125.50")` for exact arithmetic.
- **Frozen models**: Events are immutable value objects. Once created, they cannot be modified.
- **No messaging dependencies**: This package contains only Pydantic models. RabbitMQ, Kafka, or any other transport is the responsibility of the publishing/consuming service.

## Testing

```bash
cd services/shared/contracts
uv sync --dev
uv run pytest
```
