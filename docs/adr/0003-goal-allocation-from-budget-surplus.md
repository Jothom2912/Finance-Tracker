# ADR-0003: Automatic goal allocation from budget surplus

**Date:** 2026-05-01
**Status:** Accepted
**Context:** First automatic cross-service flow between the budget context, currently in the monolith and planned for `services/budget-service/`, and `services/goal-service/`.

## Decision

When a budget month closes with a positive surplus, the surplus is automatically allocated to the account's default savings goal. The flow is event-driven, idempotent, and audit-logged.

The single integration contract is `BudgetMonthClosedEvent` in `services/shared/contracts/contracts/events/budget.py`. This is a shared schema, not a shared domain model. The monolith publishes this event in v1. When `services/budget-service/` is extracted, only the publish point moves; consumers still see the same contract.

```python
from __future__ import annotations

from contracts.base import BaseEvent


class BudgetMonthClosedEvent(BaseEvent):
    """Published when an account-level budget month is closed.

    surplus_amount is calculated as:
    max(0, sum(budgeted_per_account) - sum(actual_spent_per_account)).

    The calculation is account-level in v1, not per category. Amounts are
    serialized as strings so consumers can parse them as Decimal values.
    """

    event_type: str = "budget.month_closed"
    event_version: int = 1

    account_id: int
    year: int
    month: int
    budgeted_amount: str
    actual_spent: str
    surplus_amount: str
```

The consumer-side idempotency key is:

```text
budget.month_closed:{account_id}:{year}:{month}
```

The v1 trigger is a scheduled close job on day 7 of the next month, per account. This gives late bank-synced transactions time to settle before closing the month. Bank transactions for the last day of a month can arrive 1-3 days later, so closing on day 1 risks using incomplete numbers.

## Goal-service schema

The allocation schema separates successful allocations from unallocated surplus. This keeps `goal_allocation_history.goal_id` non-null and keeps the foreign key meaningful.

```sql
CREATE TABLE goal_allocation_history (
    id              UUID PRIMARY KEY,
    source_key      VARCHAR(255) NOT NULL,
    goal_id         INTEGER NOT NULL REFERENCES goals(idGoal),
    account_id      INTEGER NOT NULL,
    amount          NUMERIC(12, 2) NOT NULL CHECK (amount > 0),
    correlation_id  UUID,
    applied_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (source_key, goal_id)
);

CREATE INDEX ix_goal_allocation_history_goal_id
    ON goal_allocation_history (goal_id);

CREATE INDEX ix_goal_allocation_history_source_key
    ON goal_allocation_history (source_key);

CREATE TABLE unallocated_budget_surplus (
    id              UUID PRIMARY KEY,
    source_key      VARCHAR(255) NOT NULL UNIQUE,
    account_id      INTEGER NOT NULL,
    amount          NUMERIC(12, 2) NOT NULL CHECK (amount > 0),
    reason          VARCHAR(50) NOT NULL,
    correlation_id  UUID,
    observed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_unallocated_budget_surplus_account_id
    ON unallocated_budget_surplus (account_id);

ALTER TABLE goals
    ADD COLUMN is_default_savings_goal BOOLEAN NOT NULL DEFAULT FALSE;

CREATE UNIQUE INDEX ix_goals_one_default_per_account
    ON goals ("Account_idAccount")
    WHERE is_default_savings_goal = TRUE;
```

Both new history tables use `CHECK (amount > 0)`. This follows the same invariant as transaction amounts: money amounts are positive, and direction or meaning is represented separately.

The `goals` table keeps the existing `"Account_idAccount"` column name because it is inherited from the current schema. New tables use `account_id`.

## Consumer logic (v1)

1. Receive `BudgetMonthClosedEvent` and parse `surplus_amount` as a `Decimal`.
2. If the parsed surplus is `0`, acknowledge the message and return. No database row is written for zero surplus or overspend.
3. Look up the default savings goal for `account_id`.
4. If no default goal exists, or the default goal is already at `target_amount`, insert into `unallocated_budget_surplus` with reason `no_default_goal` or `goal_already_complete`. The unique `source_key` makes redelivery a no-op.
5. Otherwise, in one database transaction, insert into `goal_allocation_history` and update `goals.current_amount = current_amount + amount`. The unique `(source_key, goal_id)` constraint makes redelivery a no-op.

Goals never decrement because of overspend. Good months grow goals; bad months do not shrink them.

## Alternatives considered

**A. Two events: `budget.month_closed` and `budget.surplus_calculated`.** Rejected. This is one logical fact. Two events would create two consumers and two replay paths. `budget.month_closed` is a lifecycle event, and the surplus is a derived field carried in the payload.

**B. Idempotency via `(account_id, year, month, goal_id)` instead of `source_key`.** Rejected. It is equivalent for v1, but `source_key` survives when other event sources, such as refund credits or one-off bonuses, start writing to the same history table. It is also easier to search during replay and debugging.

**C. A single `goal_allocation_history` table with nullable `goal_id`.** Rejected. PostgreSQL treats nulls as distinct in normal unique constraints, so `(source_key, NULL)` would not deduplicate redelivered messages. `NULLS NOT DISTINCT`, functional `COALESCE` indexes, or sentinel goal IDs all add complexity. More importantly, an unallocated event is not an allocation.

**D. Decrement `current_amount` on overspend.** Rejected. It creates confusing UX. A user should not lose virtual savings progress because one month went badly.

**E. Wait for budget-service extraction.** Rejected. Goal-service can consume a stable contract before the publisher moves. The contract becomes the API that the later extraction must honor.

**F. Require user approval before allocation.** Rejected for v1. It defeats the automatic event-driven flow. A future "undo last allocation" feature is cheaper than putting a user in the event loop.

**G. Per-category surplus in v1.** Rejected. Per-category allocation needs user-defined priority rules across categories. Account-level surplus is the simpler default.

## Out of scope

- Split allocations, such as 50% to vacation and 50% to emergency savings.
- Per-category surplus events.
- Cross-account allocation.
- UI for reclaiming or assigning unallocated surplus.
- Manual "close month" button.

The schema supports future split allocations without migration: use the same `source_key` and write one `goal_allocation_history` row per goal.

## Money type

`Goal.current_amount` changes from `float` to `Decimal` end-to-end in Python. The database column is already `NUMERIC(12, 2)`, so no database type migration is required. Event payloads continue to serialize money values as strings, matching the existing transaction and goal event patterns.

Consumers compare parsed `Decimal` values, not raw strings. This avoids treating `"0"`, `"0.00"`, and `"0.000"` differently.

## Consequences

- `services/shared/contracts/contracts/events/budget.py` is introduced with `BudgetMonthClosedEvent`.
- Goal-service gains a RabbitMQ consumer in addition to its current outbox publisher.
- The monolith's budget code becomes the v1 publisher.
- `is_default_savings_goal` adds API and UI surface for selecting a default goal per account.
- `GET /api/v1/goals/{goal_id}/allocation-history` exposes the audit trail.
- The architecture diagram should show the goal-service consumer arrow once the consumer is implemented.

## Re-evaluate if

- Users request split allocations. The schema is ready, but the consumer changes from "find one default goal" to "iterate allocation rules."
- Bank sync lag makes day-7 close inaccurate often enough to matter. Move the close date later or introduce manual close.
- Budget-service extraction computes surplus differently from the monolith. The published `surplus_amount` must remain identical across the cutover; otherwise, supersede this ADR with `event_version = 2`.
- A second event source writes to `goal_allocation_history` and the `source_key` format becomes ambiguous.

## v1 implementation order

Each step should be a separate commit or PR:

1. Add `BudgetMonthClosedEvent` in shared contracts. No behavior change.
2. Add `is_default_savings_goal`, the partial unique index, DTO support, and endpoint to set the default goal.
3. Add `goal_allocation_history`, `unallocated_budget_surplus`, repositories, and `GET /api/v1/goals/{goal_id}/allocation-history`.
4. Change goal money fields from `float` to `Decimal`.
5. Add the goal-service RabbitMQ consumer and tests for the v1 consumer logic.
6. Add monolith publisher and day-7 scheduled close job.
7. Add frontend support for selecting the default savings goal and reading allocation history.

After step 5, the consumer can be smoke-tested by hand-publishing `budget.month_closed` messages to RabbitMQ before the production trigger is enabled.
