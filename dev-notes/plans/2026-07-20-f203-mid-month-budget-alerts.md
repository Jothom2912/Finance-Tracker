---
title: F2-03 — Mid-month budget alerts
date: 2026-07-20
status: done            # open | in-progress | done | superseded
backlog-items: [F2-03]
related:
  - plans/2026-07-20-f101-notification-service-mvp.md
  - decisions/2026-07-17-scheduler-pattern-worker-loop.md
  - architecture/services/notification-service.md
  - architecture/services/account-budget-goal-services.md
---

# F2-03 — Mid-month budget alerts

## Goal

When a user has spent a configurable share of a budget line during the **running**
budget month, they get one in-app notification: *"80% af Dagligvarer brugt, 12 dage
tilbage."* Budgets become preventive instead of forensic. Done when: a new
`budget-alert-scheduler` worker in budget-service periodically evaluates each open
monthly budget for the current period, emits `budget.line_threshold_crossed` per line that
crosses a threshold (default 80% and 100%), notification-service turns it into a feed entry,
each (line, threshold, period) notifies **at most once**, and a full-stack e2e proves it.

## Context

F1-01 shipped the notification-service (2026-07-20) as a terminal consumer of three F1
triggers; F2-03 was explicitly unblocked by it ([FEATURES.md](../backlog/FEATURES.md)).
This is the small (S) follow-up that gets the most leverage from the fresh consumer: it
activates a **fourth trigger** on the same consumer and exercises the same owner-resolution
path already built for `budget.month_closed`.

Budget alerts are inherently **time-driven**, not event-driven: spending accrues across the
month and there is no single upstream event that says "you just crossed 80%". So the trigger
is a scheduler, reusing the settled worker-loop pattern
([scheduler-decision](../decisions/2026-07-17-scheduler-pattern-worker-loop.md), first used
by F1-07's month-close scheduler — the direct template here).

**Key design decision — idempotency lives downstream, scheduler stays stateless.**
The scheduler re-evaluates every tick and emits a crossing event whenever a line is at/over a
threshold. It keeps **no memory** of what it already fired. Uniqueness ("once per line per
threshold per period") is enforced by notification-service's existing **unique `source_key`**
backstop (the IntegrityError→ACK path). Trade-off we accept: every tick republishes all
active crossings → some redundant outbox rows + consumer work + benign IntegrityErrors. Why
acceptable: (a) volume is tiny (few budgets × few lines × 2 thresholds) and the interval is
coarse (default 6h); (b) it avoids a *new* `budget_alerts_sent` state table that would
duplicate computable/idempotency information — exactly the "stored state duplicating
computable info" anti-pattern CLAUDE.md warns against; (c) it matches the repo's self-healing
/ idempotent-consumer philosophy where the DB constraint is the single source of truth for
"already handled". The alternative (track fired alerts in budget-service) is rejected for the
extra sync surface.

**Second decision — event is account-scoped, owner resolved in notification-service.**
`BudgetLineThresholdCrossedEvent` carries `account_id` (not `user_id`), matching
`BudgetMonthClosedEvent` and `GoalReachedEvent`. This reuses notification-service's single
owner-resolution mechanism (`IAccountOwnerPort` → account-service) verbatim rather than
introducing a second, user_id-bearing code path. Cost accepted: account-service must be up
for alerts to be delivered (an extra HTTP hop even though the budget row already knows
`user_id`). Acceptable because it keeps "notification-service owns the account→user mapping"
invariant intact and reuses the exact handler shape of `handle_budget_month_closed`.

## Non-goals

- **No change to `close_month` / `budget.month_closed` / surplus→goal allocation.** The alert
  scheduler is a *new, read-only* trigger; it never mutates budgets, never closes anything.
- **No new spent-computation path semantics.** Reuse `ITransactionPort.get_expenses_by_category`
  with **fail-closed** behaviour (retry next tick if transaction-service is down) — we do NOT
  adopt `get_summary`'s fail-open (spent=0) path, so a down upstream means *no* alert that
  tick, never a false "0% used". (Independent of the fail-open surplus-fabrication CRITICAL,
  which this plan does not touch.)
- **No frontend rewrite.** The `NotificationBell` renders any notification's title/body
  generically; the new type shows up automatically. Optional: a bell icon/label mapping for
  the new `NotificationType` (small, in scope but non-blocking).
- **No email.** Stays on the deferred `IEmailPort` + `LogEmailAdapter` no-op path.
- **No per-budget custom start-day or per-user threshold config** — MVP uses calendar-month
  period (`start_day=1`, matching `get_summary`'s default) and a service-wide threshold list.

## Steps

### A. Shared contracts — new event

1. [ ] `services/shared/contracts/contracts/events/budget.py` — add
   `make_budget_line_threshold_crossed_source_key(account_id, year, month, category_id, threshold) -> str`
   returning `f"budget.line_threshold_crossed:{account_id}:{year}:{month}:{category_id}:{threshold}"`
   (threshold in the key ⇒ 80% and 100% are distinct notifications), and
   `BudgetLineThresholdCrossedEvent(BaseEvent)` with `event_type = "budget.line_threshold_crossed"`,
   fields: `account_id:int, year:int, month:int, category_id:int, category_name:str,
   budgeted_amount:str, spent_amount:str` (decimal-strings + `@field_validator` like the
   month-closed event), `percentage_used:int, threshold:int, days_remaining:int`, and a
   `@property source_key`. Export it in
   `services/shared/contracts/contracts/events/__init__.py`.
2. [ ] Test: round-trip (`to_json`/`from_json`) + `source_key` shape + threshold distinctness
   in the contracts test suite.

### B. budget-service — domain: days-remaining + crossing evaluation

3. [ ] `services/shared/domain/domain/budget_period.py` — add pure
   `days_remaining_in_period(year, month, today: date, start_day: int = 1) -> int` = days from
   `today` to inclusive `end_date` (from `budget_period`), **floored at 0** if `today` past
   period end. Injected `today` (no wall-clock). Unit-test: mid-period, last day (=0 or 1 per
   inclusive convention — pick and document), `today` after end (→0), leap-year Feb, day-28
   clamp.
4. [ ] `services/budget-service/app/domain/` — pure `evaluate_line_crossings(lines, spent_by_category, thresholds) -> list[Crossing]`
   where each `Crossing` = `(category_id, budget_amount, spent_amount, percentage_used, threshold)`.
   Rules: skip lines with `amount <= 0` (no division by zero, no alert); `pct = spent/amount*100`;
   for each threshold in `thresholds`, emit one crossing when `pct >= threshold`. Multiple
   thresholds ⇒ multiple crossings (80 and 100 both fire when >100%). Unit-test: below/at/above
   80, at/above 100, `amount=0` skipped, missing category in spent map ⇒ spent 0 ⇒ no crossing,
   multiple lines.

### C. budget-service — application: evaluate-alerts use case

5. [ ] `services/budget-service/app/application/monthly_budget_service.py` (or a small new
   `alert_service.py`) — `async def evaluate_alerts(self, budget, today, thresholds, user_id) -> list[BudgetLineThresholdCrossedEvent]`:
   compute `budget_period(year, month, 1)`, call `get_expenses_by_category` (**fail-closed** —
   let `UpstreamServiceUnavailable` propagate), resolve category names via `ICategoryPort`
   (denormalize `category_name` into the event; on name-lookup failure fall back to
   `str(category_id)` — never crash an alert), compute `days_remaining_in_period`, run
   `evaluate_line_crossings`, and build one event per crossing. **Emit via the outbox** in the
   same UoW (`self._uow.outbox.add(event, "monthly_budget", str(budget.id))` + commit) —
   publisher routes by `event_type` automatically (no publisher change).
6. [ ] `services/budget-service/app/adapters/outbound/postgres_monthly_budget_repository.py`
   \+ its port interface — add `list_open_for_period(year, month) -> list[MonthlyBudget]`
   (`closed_at IS NULL` AND period == given period; NOT user-scoped — scheduler acts per-row
   `user_id`, mirroring `list_open_before_period`).

### D. budget-service — the scheduler worker

7. [ ] `services/budget-service/app/workers/budget_alert_scheduler.py` — copy the shape of
   `month_close_scheduler.py`: `main()` loop reads `today`, calls `run_once(...)` in try/except,
   sleeps `settings.BUDGET_ALERT_INTERVAL_SECONDS`. `run_once(session_factory, today, thresholds, transaction_port=None, category_port=None)`:
   fetch `list_open_for_period(today.year, today.month)`; **one session per budget**; call
   `evaluate_alerts`; isolate per-budget failures; catch `UpstreamServiceUnavailable` (skip,
   retry next tick), bare `Exception` (log, continue). Return counters dict. Injected `today`
   \+ injectable ports for tests. Unit-test `run_once` with fakes: open-for-period filter,
   crossing→event emitted to outbox, upstream-down ⇒ no events + no crash, no-crossing ⇒ 0
   events.
8. [ ] `services/budget-service/app/config.py` — add `BUDGET_ALERT_INTERVAL_SECONDS: int = 21600`
   (6h) and `BUDGET_ALERT_THRESHOLDS: list[int] = [80, 100]` (or comma-string parsed to ints —
   match existing settings style).

### E. notification-service — consume the new trigger

9. [ ] `services/notification-service/app/workers/notification_consumer.py` — add
   `"budget.line_threshold_crossed"` to `ROUTING_KEYS`; add `_dispatch` branch parsing
   `BudgetLineThresholdCrossedEvent` → `handle_budget_line_threshold_crossed`.
10. [ ] `services/notification-service/app/application/service.py` — new handler mirroring
    `handle_budget_month_closed`: build content via new message fn, resolve owner
    (`self._account_owner.get_owner_user_id(event.account_id)`; `AccountNotFound`→drop/ACK,
    `AccountOwnerUnavailable`→propagate for retry/DLQ), `_create(user_id, content, event.source_key)`.
11. [ ] `services/notification-service/app/domain/entities.py` — add
    `NotificationType.BUDGET_THRESHOLD_CROSSED`. **Verify `notifications.type` is a free
    string column, not a native PG enum** — if it's a DB enum, add an alembic migration to
    extend it; if string (expected), no migration.
12. [ ] `services/notification-service/app/domain/messages.py` — add
    `build_budget_line_threshold_crossed(event) -> NotificationContent` producing e.g. title
    "Budget-advarsel" / body `"{pct}% af {category_name} brugt, {days} dage tilbage."`
    (reuse `format_amount` if we also show kr.; handle `days_remaining==0` → "sidste dag" /
    "ingen dage tilbage"; singular "1 dag"). Unit-test the Danish text.
13. [ ] Optional: frontend `NotificationBell` icon/label mapping for the new type
    (`services/.../frontend`), non-blocking.

### F. Infra

14. [ ] `docker-compose.yml` — add `budget-alert-scheduler` service (same budget image,
    `command: python -m app.workers.budget_alert_scheduler`, single replica, budget env +
    new vars, `depends_on` postgres-budget + rabbitmq healthy), mirroring
    `budget-month-close-scheduler`.
15. [ ] Makefile targets + k8s deferred (same as other schedulers); CI matrix already covers
    budget-service + notification-service.

### G. Verification

16. [ ] **Unit** — `make -C services/budget-service test` (domain days-remaining + crossings +
    scheduler run_once), `make -C services/notification-service test` (handler + message +
    dedup), contracts test. `ruff` + `bandit` + frontend lint/build clean.
17. [ ] **Live e2e (full stack)** — create a monthly budget for the *current* period with a
    line (e.g. Dagligvarer, budget 1000); create transactions summing ~850 (85%) on that
    account/category/period; run one scheduler tick (invoke `run_once` or start the container /
    temporarily shrink the interval). Expect: `budget.line_threshold_crossed` (threshold 80) →
    notification "85% af Dagligvarer brugt, N dage tilbage" for the owner. Push spend over
    100% → next tick fires the **100** threshold (distinct source_key) → second notification.
    Run the tick again with no new spend → **no duplicate** (source_key dedup, 1 row each).
    Verify a second user sees 0 (owner-scoping). Ensure `budget-outbox-worker` is *running*
    (F1-01 e2e gotcha: schedulers/workers sometimes sit in `created` — `docker compose up -d`).

## Risks & rollback

- **Notification spam / churn** from stateless re-emit. Mitigation: coarse default interval
  (6h) + downstream unique-`source_key` dedup means the *user* sees one notification per
  crossing regardless of tick count; only internal outbox/consumer churn is redundant, and
  it's bounded by budget×line×threshold count. Detect via notification-service logs
  (IntegrityError-ACK rate) and outbox row growth. If it ever matters, add a lightweight
  "already emitted" guard (deferred by decision above).
- **Fail-open spent** would fabricate a false "0% used" (no alert) or, worse if we'd reused
  `get_summary`, wrong percentages. Mitigation: use fail-closed `get_expenses_by_category`;
  down upstream ⇒ skip tick. Under-notify, never mis-notify.
- **days_remaining baked at first crossing** (dedup means later ticks don't update the text).
  Accepted: it's a point-in-time alert; the crossing moment is the informative one.
- **Time-nondeterminism in tests** — all domain fns take injected `today: date`; scheduler
  `run_once` takes `today`; no `datetime.now()` in domain (CLAUDE.md).
- **Rollback**: the feature is additive and isolated. Stop/remove the `budget-alert-scheduler`
  container → no more alerts; the event contract, unused handler, and enum member are inert.
  No schema change to existing tables (only possibly a notification-type enum extension, which
  is backward-compatible).

## Outcome (done 2026-07-20)

Shipped in 7 commits (A–G, commit-per-phase): contracts event → budget domain →
budget application/repo → scheduler worker → notification consumer → compose → e2e.
Live full-stack e2e **PASSED 4/4** (`tests/e2e/test_budget_threshold_alert_e2e.py`):
80% notification "85% af Diverse brugt, 13 dage tilbage" (Budget-advarsel), distinct
100% "125% af … " (Budget overskredet), re-tick keeps exactly 2 rows (source_key
dedup), foreign user sees 0. Scheduler container live-verified doing real ticks.

Test totals green: contracts 53, shared-domain 42, budget-service 60 unit + 42
integration, notification-service 60. ruff clean across touched services.

**Deviations from plan**
- `notifications.type` is a `String(50)` column, **not** a native PG enum → the new
  `BUDGET_THRESHOLD_CROSSED` member needed **no migration** (plan's flagged risk void).
- No frontend change: `NotificationBell` already renders title/body generically; the
  optional per-type icon was skipped (no icon system exists to extend).
- Makefile untouched — it doesn't reference schedulers by name; CI matrix already
  covers both services.

**Gotcha discovered during e2e (worth remembering)**
- Async **re-categorization** in transaction-service moves a transaction's
  `category_id` *after* create (seed-id → rule-matched id, e.g. 11→8). `close_month`
  is immune (it sums all categories) but the **per-line** alert matches one category,
  so the e2e had to budget against the *settled effective* category (poll the tx DB
  for two identical reads before creating the budget line). Any future per-category
  feature/test faces the same race.

**Follow-ups spawned**
- None required. Email still deferred (`IEmailPort`/log adapter). The stateless
  re-emit churn (accepted) can get an "already-emitted" guard later if volume grows;
  not needed at current scale.
