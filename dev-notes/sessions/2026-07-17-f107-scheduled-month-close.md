---
date: 2026-07-17
topic: F1-07 shipped — day-7 auto-close scheduler; scheduler pattern decided (worker-loop)
---

# F1-07: scheduled day-7 month-close

Plan: [plans/2026-07-17-f107-scheduled-month-close.md](../plans/2026-07-17-f107-scheduled-month-close.md).
One code commit (`42824490`) + docs; planned and shipped same day (same session as P3-16).

## Done

- **Scheduler-pattern decision** (blocks F1-05 too): in-service worker-loop containers
  (outbox-worker shape), NOT KEDA cron — compose is the primary runtime and a
  scheduling mechanism that only runs in k8s never runs in dev.
  [decisions/2026-07-17-scheduler-pattern-worker-loop.md](../decisions/2026-07-17-scheduler-pattern-worker-loop.md)
  — rules: idempotency in the data layer, single replica, missed ticks self-heal,
  clock injected into due-logic.
- **Domain due-rule** `app/domain/scheduled_close.py`: due from day `close_day` (7) in
  the following month; older months overdue; December-rollover tested.
- **Sweep query** `list_open_before_period` (closed_at IS NULL + period tuple-compare).
- **Worker** `app/workers/month_close_scheduler.py`: `run_once` (testable core) +
  loop shell; per-budget session + exception isolation (AlreadyClosed → INFO race,
  UpstreamServiceUnavailable → WARNING retry next tick, unexpected → ERROR continue);
  tick-summary log. Same `close_month` use case as the button — fail-closed (P1-01),
  same event, same 409s.
- **Compose**: `budget-month-close-scheduler` (env `MONTH_CLOSE_INTERVAL_SECONDS`=3600,
  `MONTH_CLOSE_DAY`=7). 42 tests + lint green (5 sweep tests against sqlite with
  injected ports, 11 due-rule cases).

## Live e2e (compose): PASSED

Synthetic goal 18 + budgets 2025-10/11 on account 1; scheduler run with 15s interval:
1. Open past month 2025-10 (120): first tick → **auto-closed, goal +120 + history row**.
2. Manually pre-closed 2025-11: **never a candidate** (sweep filters closed_at).
3. Next tick: **0 candidates** — idempotent.
Cleanup: synthetic rows removed, goal 15 rolled back (a manual-close side-effect
credited it 60 kr mid-test) and restored as default; prod-config scheduler (3600s)
now running in the stack with 0 candidates.

## Learned / gotchas

- **In-memory sqlite + `Base.metadata.create_all` requires `import app.models` first**
  — in the first test of a session the models aren't registered yet, so create_all
  silently creates zero tables ("no such table" only when THAT test runs first).
- budget-service tests need `PYTHONPATH=../../services/shared/contracts` (Makefile does
  it) — bare `uv run pytest` can't import contracts.
- `aiosqlite` was missing from budget-service dev-deps (integration tests use
  testcontainers) — added for the sqlite-based worker tests.
- E2e ordering matters: closing a synthetic budget while the REAL default goal is
  active credits the real goal — set the synthetic default goal BEFORE any close.
  (Rolled back via psql: decrement + delete history row.)
- P3-16's soft-delete was exercised in anger during cleanup: DELETE of goal 18 (which
  had allocation history) → 204. Regression confirmed fixed in a second live flow.

## Open ends

- Scheduler track continues: **P3-14** (serialize bank-sync sagas per connection, S)
  → **F1-05** (scheduled bank sync, reuses the worker-loop pattern). Then F1-01
  notifications (auto-close/auto-sync events now exist to notify about).
- k8s manifests don't include the new worker (deliberate non-goal; add when k8s is
  next touched).
