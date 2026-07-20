---
date: 2026-07-20
topic: F2-03 shipped — mid-month budget alerts (4th notification trigger)
---

# Session 2026-07-20 — F2-03 mid-month budget alerts

Plan: [plans/2026-07-20-f203-mid-month-budget-alerts.md](../plans/2026-07-20-f203-mid-month-budget-alerts.md).
Shipped in 7 commits (commit-per-phase A–G). Second feature of the day after F1-01/F1-08.

## Done

- **A — contracts** (`f265de8e`): `BudgetLineThresholdCrossedEvent` (account-scoped;
  `category_name`, `percentage_used`, `threshold`, `days_remaining`; source_key includes
  threshold so 80/100 dedup independently). Exported in both `__init__`s. +8 tests.
- **B — domain** (`fc7811b6`): shared `days_remaining_in_period` (injected `today`, floored
  at 0); budget-service `evaluate_line_crossings` (skips ≤0-budget lines → no div-by-zero;
  deterministic order). +10 + days-remaining tests.
- **C — application** (`5c03c807`): `MonthlyBudgetService.evaluate_alerts` (fail-closed
  spent like `close_month`; denormalizes `category_name` w/ id-fallback; outbox emit in one
  commit) + repo `list_open_for_period`. +5 tests.
- **D — scheduler** (`0a2a9cf1`): `budget_alert_scheduler.py` worker-loop (per-budget failure
  isolation, upstream-down skip+retry) + config `BUDGET_ALERT_INTERVAL_SECONDS`/`_THRESHOLDS`.
  +7 run_once tests against sqlite.
- **E — notification** (`453bbe60`): 4th trigger on the same consumer — routing key + dispatch
  + `handle_budget_line_threshold_crossed` (owner resolved via `IAccountOwnerPort`) + new
  `BUDGET_THRESHOLD_CROSSED` type + Danish builder (warning vs overspend). +15 tests.
- **F — compose** (`a1e89f5c`): `budget-alert-scheduler` container.
- **G — e2e** (`e185dfe4`): `tests/e2e/test_budget_threshold_alert_e2e.py`, **PASSED 4/4** live.

## Live e2e (full stack): PASSED

- Registered user → default account → seeded 2 expenses (850) → budget line 1000.
- Drove `run_once(today=2026-07-18, [80,100])` in the budget-service container.
- **80%**: notification "85% af Diverse brugt, 13 dage tilbage" (title *Budget-advarsel*).
- Pushed spend to 1250 → **100%**: distinct notification "125% af Diverse brugt, 13 dage
  tilbage" (title *Budget overskredet*), separate source_key.
- Re-tick with no new spend → still exactly **2** rows (source_key dedup).
- Fresh user's feed → **0** (owner-scoping).
- Started the `budget-alert-scheduler` container; observed a real tick
  ("5 open budgets, 6 events emitted, 0 upstream-failed").

Test totals green: contracts 53, shared-domain 42, budget 60 unit + 42 integ, notification 60.

## Learned / surprised

- **Async re-categorization races per-category reads.** transaction-service moves a
  transaction's `category_id` *after* create (seed-id → rule-matched id, seen 11→8). This is
  invisible to `close_month` (sums all categories) but breaks the **per-line** alert unless
  the budget line is on the *effective* category. The e2e now polls the tx DB for two
  identical reads before budgeting. **Any future per-category feature/test hits this.**
- `notifications.type` is a **`String(50)`** column, not a native PG enum → new enum members
  need **no migration**. (Plan had flagged this as a risk; it's void.)
- The topic-exchange fan-out made the new trigger nearly free: publisher routes by
  `event_type`, so **zero** budget-side publisher changes; only the consumer bind + handler.
- `budget-outbox-worker` must be running for the outbox to drain (same F1-01/F1-08 local
  gotcha) — rebuild + `up -d` the budget containers so they carry the new code + contracts.

## Open ends

- Email still deferred (`IEmailPort` + `LogEmailAdapter` no-op) — shared with F1-01.
- Stateless re-emit churn is accepted at current scale; an "already-emitted" guard is a
  later option if volume grows.
- k8s manifest for the new scheduler deferred (same as the other scheduler containers).
- F2 remaining: F2-01 recurring, F2-02 forecast, F2-04 semantic search UI, F2-05 report
  export, F2-06 AI chat expansion, F2-07 month-picker cleanup.

## Notes updated

- Plan set `status: done` + Outcome.
- `backlog/FEATURES.md` F2-03 → done.
- `architecture/services/notification-service.md` (4th trigger row) +
  `architecture/services/account-budget-goal-services.md` (alert-scheduler + producer event).
- `00-INDEX.md` (plan + this session).
