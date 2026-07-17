---
title: P3-16 — Goal soft-delete (fix FK 500 on delete with allocation history)
date: 2026-07-17
status: done
backlog-items: [P3-16]
related:
  - ../findings/2026-07-17-goal-delete-fk-500.md
  - ../plans/2026-07-17-f104-goal-allocation-completion.md
  - ../decisions/2026-07-17-manual-month-close-button.md
---

# P3-16 — Goal soft-delete

## Goal

`DELETE /api/v1/goals/{id}` works on any owned goal — including one with
`goal_allocation_history` rows — without a 500, while the allocation audit trail is
preserved in the DB. Done when: deleting a goal with history returns 204, the goal
disappears from all read paths (list, get, default-goal lookup), the month-close
consumer can never allocate to a deleted goal, and the history rows still exist in
Postgres.

## Context

Finding [F-2026-07-17-01](../findings/2026-07-17-goal-delete-fk-500.md): goals are
hard-deleted (`AsyncPostgresGoalRepository.delete` → `session.delete`), but
`goal_allocation_history.goal_id` has a plain FK with no ON DELETE behavior →
`IntegrityError` bubbles as 500. Found live during the F1-04 e2e cleanup.

**Choice: soft-delete** (`deleted_at` timestamp). This is already the CLAUDE.md
convention for domain entities — goals just predate the rule. Alternatives from the
finding, rejected:
- *409-guard* ("goals with history cannot be deleted") — honest but hostile: after
  F1-04 every default goal accumulates history within a month, making most goals
  permanently undeletable.
- *Cascade-delete history* — destroys the audit trail documenting where money went.

The critical invariant (also from the finding): **the default-flag must never point at
a deleted goal**, or the month-close consumer would allocate money into it. We enforce
this by clearing `is_default_savings_goal` in the same UPDATE that sets `deleted_at`,
plus a defensive `deleted_at IS NULL` filter in the consumer's default-goal lookup.

## Non-goals

- No behavior change for the API surface: delete still returns 204/404, still emits
  `GoalDeletedEvent` (downstream consumers — analytics ES projection — keep treating
  it as a deletion; they never need to know it's soft).
- No un-delete/restore endpoint, no "vis slettede mål" UI. Deleted goals are simply
  invisible; their history is DB-only audit data (acceptable: reachable via psql,
  not product surface).
- No change to allocation/unallocated tables, the handler's status ladder, budget-service,
  or the frontend (a soft-deleted goal disappears from the list exactly like a hard
  delete did).
- No `datetime.now()` in domain logic: the timestamp is set server-side via `func.now()`
  in the adapter.

## Steps

1. [ ] **Migration 005** — `migrations/versions/005_add_goals_deleted_at.py`:
   `ALTER TABLE goals ADD COLUMN deleted_at TIMESTAMPTZ NULL` (nullable, no default, no
   backfill — no deleted rows exist yet). Use `batch_alter_table` for sqlite parity and
   write a real downgrade (drop column) — both lessons from the migration-004 finding.
   The partial unique index `ix_goals_one_default_per_account` needs no change: delete
   clears the flag, so a deleted row can never hold it.
2. [ ] **Model + reads** — `app/models.py`: `deleted_at: Mapped[datetime | None]`
   (DateTime(timezone=True)). `app/adapters/outbound/postgres_goal_repository.py`:
   - `delete()` → single `UPDATE … SET deleted_at = func.now(),
     is_default_savings_goal = false WHERE idGoal = :id AND deleted_at IS NULL`;
     return `rowcount == 1` (second delete → False → 404, same as today).
   - `get_by_id` / `get_all` add `deleted_at IS NULL`.
   - `set_default_savings_goal` adds `deleted_at IS NULL` to the SET-half's WHERE
     (unreachable via service — `get_by_id` 404s first — but cheap belt-and-braces).
   - `app/adapters/outbound/postgres_goal_allocation_repository.py`:
     `get_default_savings_goal` adds `deleted_at IS NULL` (defensive; documents the
     invariant against manual DB edits).
   The `Goal` domain entity does NOT get the field — no read path ever returns a
   deleted goal, so exposing it would be dead state.
3. [ ] **Tests** — goal-service suite:
   - Repo: delete sets `deleted_at` + clears default flag + row survives in table;
     deleted goal invisible to `get_by_id`/`get_all`/`get_default_savings_goal`;
     double-delete returns False.
   - Service: delete of goal **with allocation-history rows** succeeds and emits
     `GoalDeletedEvent` (the regression test for the finding).
   - Handler: month-close for an account whose default goal was just deleted →
     `unallocated_no_default_goal` (not an allocation).
   - Migration test: extend the sqlite up/down suite with 005 (fixture already
     monkeypatches DATABASE_URL per wave 0).
4. [ ] **Verification** — `make -C services/goal-service test` + lint green; then live
   compose e2e (reuse the F1-04 synthetic pattern — goal on account 1, past months
   2025-xx): create goal → set default → close month → history row exists → **DELETE
   goal → 204** → goal gone from `GET /goals`, `psql`: row has `deleted_at`, history
   row intact → close another month → unallocated-row with `no_default_goal`.
5. [ ] **Docs close-out** — finding F-2026-07-17-01 → `status: resolved`; P3-16 → done;
   update `architecture/services/account-budget-goal-services.md` (de-flag the ⚠, note
   soft-delete); session log; this plan → done + Outcome.

## Risks & rollback

- **Missed read path** keeps showing deleted goals: goal-service is the only reader of
  its DB (database-per-service), and all `GoalModel` selects live in the two adapter
  files touched above — grep `select(GoalModel)` as the completeness check. Gateway
  reads goals via HTTP (`/goals?account_id=`), so it inherits the filter.
- **Deleted default goal still receiving allocations** would be money-corruption: guarded
  three ways (flag cleared in the delete UPDATE, `deleted_at IS NULL` in the consumer
  lookup, handler test). Detectable via allocation-history rows pointing at a goal with
  `deleted_at` set.
- **Rollback**: revert the code commit and downgrade migration 005; soft-deleted rows
  would resurface as live goals (acceptable for a rollback window — they were
  user-deleted, not corrupted).

## Outcome (fill in when done)

Shipped same day in one code commit (5cd613e5) + docs. Executed as planned with three
small additions beyond the written steps:

- `update()` also got the `deleted_at IS NULL` filter (updating a deleted goal now
  raises instead of silently resurrecting data) — found via the plan's
  `select(GoalModel)` completeness grep.
- The FK regression test enables `PRAGMA foreign_keys=ON` explicitly — the sqlite test
  setup does not enforce FKs, so without the pragma the test would have passed even
  against the old hard-delete.
- One pre-existing integration test asserted the row was physically gone after DELETE;
  updated to assert soft-delete semantics (row present, `deleted_at` set).

Verified: 91 tests + lint green; migration 005 applied cleanly on the live Postgres at
container start; live e2e passed end-to-end (delete-with-history → 204, re-delete →
404, row soft-deleted with default-flag cleared, history intact, next month-close →
`no_default_goal` unallocated). Synthetic data cleaned up, real default goal restored.
No follow-ups spawned. Session log:
[sessions/2026-07-17-p316-goal-soft-delete.md](../sessions/2026-07-17-p316-goal-soft-delete.md).
