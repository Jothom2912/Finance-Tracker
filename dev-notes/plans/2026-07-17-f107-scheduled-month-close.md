---
title: F1-07 — Scheduled day-7 month-close (ADR-0003's original v1 trigger)
date: 2026-07-17
status: done
backlog-items: [F1-07]
related:
  - ../decisions/2026-07-17-scheduler-pattern-worker-loop.md
  - ../decisions/2026-07-17-manual-month-close-button.md
  - ../plans/2026-07-17-f104-goal-allocation-completion.md
---

# F1-07 — Scheduled day-7 month-close

## Goal

Open budget months close automatically once they are safely in the past: on day 7 of
the following month (ADR-0003's rationale — bank transactions can lag 1–3 days), a
scheduler closes every still-open budget for past periods, which triggers the existing
surplus→goal allocation. Done when: a worker container runs the sweep on an interval,
a synthetic past-month budget is auto-closed live end-to-end (goal credited), the
manual button keeps working as an override, and a month already closed by hand is
skipped silently.

## Context

- F1-04 made month-close reachable via a button; the [manual-close decision](../decisions/2026-07-17-manual-month-close-button.md)
  explicitly spawned F1-07 as the systematic fix for "user forgets to close" and
  "closed too early on incomplete numbers".
- The mechanism choice (worker-loop container, not KEDA cron) is recorded in
  [decisions/2026-07-17-scheduler-pattern-worker-loop.md](../decisions/2026-07-17-scheduler-pattern-worker-loop.md) — F1-05 will reuse it.
- Everything downstream already exists and is idempotent: `close_month` is fail-closed
  (P1-01) with a 409-guard (`mark_closed` … `WHERE closed_at IS NULL`), and the
  goal-side consumer dedups on `source_key`. The scheduler is *only* a new trigger.
- Blast-radius check on the live dev DB (2026-07-17): exactly one budget exists
  (2026-07, current month, open) — first due 2026-08-07. Enabling the scheduler live
  closes nothing today.

## Non-goals

- **No change to close semantics**: same use case (`MonthlyBudgetService.close_month`),
  same fail-closed behavior, same event, same 409 rules. The manual button stays as
  an override (close *before* day 7 remains a deliberate user action).
- **No re-close / no catch-up events**: already-closed months are skipped (`MonthlyBudgetAlreadyClosed` logged at INFO).
- `budget_start_day` stays at its default (1, calendar months) for scheduled closes —
  same as the UI button. Custom start days remain manual-only until something needs
  them.
- No notification when a month auto-closes — that's F1-01's job later.
- No k8s manifest work; compose only (the k8s demo can adopt the container later).

## Steps

1. [ ] **Domain due-rule** — `services/budget-service/app/domain/scheduled_close.py`:
   pure function `is_due_for_scheduled_close(year: int, month: int, today: date,
   close_day: int = 7) -> bool`, true iff `today >= date(<next period>, close_day)`
   (handles December→January rollover). Clock injected as `today` param — the worker
   shell is the only wall-clock reader. Unit tests: day 6 vs 7 boundary, much older
   months, December rollover, close_day override.
2. [ ] **Repo query** — `postgres_monthly_budget_repository.py` + outbound port:
   `list_open_before_period(year: int, month: int) -> list[MonthlyBudget]` — rows with
   `closed_at IS NULL AND (year, month) < (:year, :month)` (tuple comparison as
   `year < :y OR (year = :y AND month < :m)`). Rows carry `user_id`, so the scheduler
   closes each budget as its owning user — no new auth surface beyond the S2S header
   `transaction_port` already mints.
3. [ ] **Worker** — `app/workers/month_close_scheduler.py` (shape of
   `outbox_publisher.py`): asyncio loop, env-tunables `MONTH_CLOSE_INTERVAL_SECONDS`
   (default 3600) + `MONTH_CLOSE_DAY` (default 7). Each tick, in a fresh session/UoW:
   list open past-period budgets → filter with the domain rule → `close_month(...)`
   per budget with per-budget exception isolation:
   `MonthlyBudgetAlreadyClosed` → INFO (lost race to the button — fine);
   `UpstreamServiceUnavailable` → WARNING, retry next tick (fail-closed inherited);
   unexpected → ERROR, continue with remaining budgets. Tick-summary log line.
   Testable core: extract `run_once(session_factory, today, close_day)` so tests drive
   ticks with a frozen date and the loop shell stays trivial.
4. [ ] **Compose** — new service `budget-month-close-scheduler` (budget-service image,
   `command: python -m app.workers.month_close_scheduler`, env copied from
   `budget-outbox-worker` + the two tunables, `restart: on-failure`, depends_on
   budget-service healthy — matching P2-16 conventions).
5. [ ] **Tests** — unit: domain rule (step 1) + `run_once` with mocked service
   (closes due, skips not-due, isolates per-budget failure, tolerates AlreadyClosed).
   Integration: repo query against sqlite (open/closed × past/current periods);
   `run_once` end-to-end against sqlite with a stubbed transaction port asserting
   `closed_at` set + outbox row written.
6. [ ] **Verification** — `make -C services/budget-service test` + lint green. Live
   e2e (F1-04 synthetic pattern, account 1, past month, cleanup + default-goal restore
   after): create synthetic goal + default, create budget 2025-10 (e.g. 120), start
   scheduler container with `MONTH_CLOSE_INTERVAL_SECONDS=15` → observe auto-close in
   logs → goal +120 & history row ~2s later → re-tick skips (no duplicate close, INFO
   log) → manual-close race: create+close 2025-11 by button first, next tick logs the
   skip. Then reset interval to default.
7. [ ] **Docs close-out** — FEATURES.md F1-07 → done (and F1-05's "Needs first" note
   updated: scheduler pattern now exists); arch docs (budget-service section: new
   worker; infrastructure.md compose topology); session log; this plan → done +
   Outcome.

## Risks & rollback

- **Auto-closing on incomplete numbers**: day-7 rule is exactly ADR-0003's mitigation;
  the fail-closed guard (P1-01) already refuses to close when spend data is
  unavailable, and the manual button remains for humans who want earlier/deliberate
  closes.
- **Mass-close on first deploy**: by design the first tick sweeps ALL historical open
  budgets. Verified harmless in the live dev DB today (one current-month budget).
  For any future environment with real backlog: the sweep credits *real* surpluses to
  *real* default goals — that is the feature working, but deployment should be done
  eyes-open; noted in the compose service as a comment.
- **Double-trigger races** (scheduler vs button, or crash-restart mid-sweep): safe by
  layered idempotency — `mark_closed`'s conditional UPDATE (one winner) and goal-side
  `source_key` dedup (no double allocation). This is tested, not assumed.
- **Rollback**: stop/remove the compose service — the trigger disappears, manual
  button unaffected. No schema changes in this feature.

## Outcome (fill in when done)

Shipped same day in one code commit (`42824490`) + docs. Executed as planned; the only
deviations were test-infra: `aiosqlite` added to budget-service dev-deps (sweep tests
run against sqlite with injected ports), and `run_once` grew injectable
`transaction_port`/`category_port` params for exactly that.

Verified: 42 tests + lint green; live e2e passed — open past month auto-closed on the
first 15s-tick (goal +120 + history row), a manually pre-closed month was never a
candidate, next tick swept 0. The prod-config scheduler container (3600s/day-7) is now
part of the compose stack. During cleanup, P3-16's soft-delete handled a
goal-with-history deletion (204) in a second real flow.

Follow-ups: none new — next in track are the pre-existing P3-14 → F1-05 (reuse the
worker-loop pattern). k8s manifests deliberately not updated (non-goal). Session log:
[sessions/2026-07-17-f107-scheduled-month-close.md](../sessions/2026-07-17-f107-scheduled-month-close.md).
