---
date: 2026-07-17
topic: P3-16 shipped — goal soft-delete fixes FK 500 on delete-with-history
---

# P3-16: goal soft-delete

Plan: [plans/2026-07-17-p316-goal-soft-delete.md](../plans/2026-07-17-p316-goal-soft-delete.md).
One code commit (`5cd613e5`) + docs; planned and shipped same day.

## Done

- Migration 005: nullable `deleted_at TIMESTAMPTZ` on `goals` (batch_alter_table,
  real downgrade — both lessons from F-2026-07-12-01 applied).
- `AsyncPostgresGoalRepository.delete` → single UPDATE stamping `deleted_at` AND
  clearing `is_default_savings_goal` (the money-safety invariant: the month-close
  consumer can never allocate to a deleted goal). `rowcount == 1` return keeps
  204/404 semantics; second delete → 404.
- `deleted_at IS NULL` filters on `get_by_id`/`get_all`/`update`/
  `set_default_savings_goal` + defensive filter in the consumer's
  `get_default_savings_goal`. Completeness verified by grepping `select(GoalModel)`.
- `GoalDeletedEvent` still emitted — downstream (analytics ES) unchanged.
- Tests 91 green + lint: soft-delete repo suite, FK-enforced regression test,
  handler tests (deleted default goal → `unallocated_no_default_goal`, including the
  flag-survives-manual-edit case), migration 005 up/down incl. partial-index survival.

## Live e2e (compose, goal-family images rebuilt): PASSED

Synthetic goal 17 + budgets 2025-08/09 on account 1, cleaned up after; real default
(goal 15) restored:
1. Goal → default → close month (150) → **+150 allocated, history row**.
2. **DELETE goal-with-history → 204** (the old 500), re-delete → 404, gone from list;
   psql: row has `deleted_at`, flag cleared, history row intact.
3. Close next month (75) → **unallocated `no_default_goal`**.

## Learned / gotchas

- **sqlite does not enforce FKs by default** — the goal-service test DBs run without
  `PRAGMA foreign_keys=ON`, so the FK-500 regression test had to enable it explicitly;
  without the pragma it passes even against the old hard-delete. Worth remembering for
  any future FK-behavior test on sqlite fixtures.
- `GET /goals` + `unallocated-surplus` take `X-Account-ID` as a **header**, not query
  param (e2e stumbling block).
- Dev-JWT for e2e: python-jose (not pyjwt), claim `user_id`, shared dev secret —
  minted via goal-service venv.

## Open ends

- None from this work. Next track candidates unchanged from F1-04 session: F1-07
  scheduled month-close → P3-14 → F1-05 scheduled bank sync (scheduler-pattern
  decision on F1-07 first), then F1-01 notifications.
