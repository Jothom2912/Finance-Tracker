---
title: account-service + budget-service + goal-service
updated: 2026-07-07
source: architecture audit 2026-07-07
---

# account-service (8004) / budget-service (8003) / goal-service (8006)

Three sibling CRUD services with the heaviest copy-paste duplication in the repo.

## account-service — the odd one out (sync stack, monolith residue)

- **Sync** SQLAlchemy (psycopg2) + sync httpx in `def` endpoints; siblings are fully async. Worker uses **asyncpg** — same `DATABASE_URL` env needs different driver schemes per process (compose sets two different URLs; deployment footgun).
- `/api/v1/accounts` CRUD (JWT), `/api/v1/account-groups` CRUD (**no auth at all**), internal S2S `exists`/`owner` endpoints (`x-internal-api-key`).
- Table named `"Account"` with `User_idUser` column (monolith legacy); partial unique index enforces one default account per user.
- Consumer: `user.created` → create "Default Account" (calls **back into user-service** via HTTP to verify existence; failures silently drop the message — no DLQ, no requeue).
- Monolith residue: 240-line `auth.py` with unused password hashing/token minting, NEO4J/Elasticsearch config, `inspect.stack()` test detection, dead `SyncUnitOfWork`, unpinned `requirements.txt`, migrations run in API process at startup.
- Does NOT use shared contracts package — hand-rolled JSON event payloads.

## budget-service

- Async stack, UoW, pydantic-settings. **Two parallel budget domains**: legacy `/api/v1/budgets` (`budgets` table) and `/api/v1/monthly-budgets` (`monthly_budgets` + `budget_lines`, unique `(account_id, month, year)`), unsynchronized.
- `close` endpoint computes surplus (budgeted − spent via HTTP to transaction-service) and emits `budget.month_closed` with deterministic `source_key` — idempotent, well-plumbed.
- ⚠ `TransactionPort` returns `{}` on any error → `spent=0` → **whole budget fabricated as surplus** and irreversibly credited to goals (CRITICAL). `CategoryPort.exists()` also fails open.
- Mints **user JWTs for arbitrary user_ids** as service-to-service auth (`make_service_auth_header`).
- Redis URL hardcoded; summary `@cache(expire=60)` likely no-op (service instance in cache key).

## goal-service

- Async; routes defined directly in `app/main.py` (no inbound adapter module). Ownership enforced per request via account-service internal endpoints.
- `goals` (partial unique idx: one default per account), `goal_allocation_history` (unique `(source_key, goal_id)`), `unallocated_budget_surplus`.
- `budget_month_closed_consumer`: DLQ + header-based retry — the best consumer pattern in the repo; dedup on `source_key` backed by DB constraints.
- ⚠ Goal events publish `account_id` in the contract's `user_id` field (HIGH). Balance update is read-modify-write without locking (safe only at single consumer instance).

## Duplication (measured)

- outbox worker budget↔goal ~95% identical; outbox repo ~90%; rabbitmq publisher ~85%; `database.py` ~100%; `get_current_user_id` 100%; `OutboxEventModel` 100%; account's worker is a ~70% semantic re-implementation. Total ~450 LOC of outbox machinery in 3 copies (~300 redundant).
- `budget_period.py` byte-identical in account, budget AND gateway (3 copies).

## Key flows

- `user.created` → default account (fast-path skip + partial unique index + swallowed unique-violation = idempotent).
- `POST /monthly-budgets/close` → surplus → `budget.month_closed` → goal allocation to default savings goal or `unallocated_budget_surplus`.

## Open problems

See [findings/2026-07-07-architecture-audit.md](../../findings/2026-07-07-architecture-audit.md). Headliners: fail-open surplus fabrication (CRITICAL), IDOR on entire monthly-budgets API incl. close (CRITICAL), unauthenticated account-groups API (HIGH), dropped `user.created` messages (HIGH), N+1 sync HTTP inside account-group repository (HIGH), wrong identity in goal events (HIGH).
