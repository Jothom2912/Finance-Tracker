---
title: P1-13 — budget-service reads spend from analytics instead of 50 truncated rows
date: 2026-07-25
status: open
backlog-items: [P1-13]
related:
  - ../findings/2026-07-25-budget-spend-truncated-at-50.md
  - ../../docs/adr/0004-analytics-elasticsearch-read-store.md
  - ../patterns/cqrs-es-read-store.md
---

# P1-13 — budget-service reads spend from analytics instead of 50 truncated rows

## Goal

budget-service stops computing spend from a truncated transaction list and starts asking
analytics-service, the documented owner of the canonical aggregation rules (ADR-0004).

Done when: for account 1 / June 2026 the budget summary reports **16 739,83**, not
5 180,32; `close_month` derives its surplus from the same number; and the F2-03 alert
scheduler evaluates thresholds against it. Proven by re-running the exact measurement in
the finding, before and after.

## Context

[The finding](../findings/2026-07-25-budget-spend-truncated-at-50.md) — `TransactionPort`
sends no `limit`, transaction-service defaults to 50 and applies it after
`ORDER BY date DESC, id DESC`, so budget-service sums the 50 newest rows and calls it the
month. Measured: 69% understated on a real dev account-month, 41% on the currently open
one. It feeds the budget widget, `close_month`'s surplus (→ goal over-allocation) and
F2-03's alerts.

The truncation is the dominant defect but not the only one. The same loop
(`transaction_port.py:46-56`) skips `category_id is None` and counts only
`transaction_type == "expense"`, so uncategorised rows and legacy rows without a type are
invisible too. Analytics already implements the canonical rule for the latter —
`is_expense(tx_type, amount)` in
`services/analytics-service/app/domain/classification.py:26-27` falls back to the amount's
sign for typeless rows — and buckets the former explicitly as
`category_id: None → "Ukategoriseret"`. Adopting analytics removes all three at once.

Why not `&limit=10000`: it trades a silent wrong answer for a silent ceiling, leaves the
other two divergences in place, and keeps two implementations of "what counts as spend" —
which is what produced the long-tracked Forbrug-vs-budget discrepancy in the first place.

## Non-goals

- **No change to close-month semantics beyond the spend number.** The `closed_at`
  conditional UPDATE, the `MonthlyBudgetAlreadyClosed` guard, the outbox write in the same
  commit and `BudgetMonthClosedEvent`'s shape and `source_key` all stay byte-identical.
  Downstream (goal allocation, notification dedup) sees no contract change.
- **No change to fail-open/fail-closed policy.** `get_summary` keeps degrading to `spent=0`
  when the upstream is down; `close_month` and the alert scheduler keep propagating
  `UpstreamServiceUnavailable` so the month is never closed on a guess. Only the identity
  of the upstream changes.
- **No change to analytics-service.** `/overview` already returns exactly what is needed;
  this plan adds no endpoint and touches no ES mapping or projection code.
- **No change to the alert thresholds, `source_key`s or Danish message text** — F2-03's
  behaviour changes only insofar as it now sees real numbers.
- **No transaction-service change.** Its `limit=50` default is correct for a list endpoint;
  the bug is the caller treating a page as a total.
- **Not P2-24.** This adds a fourth hand-rolled internal HTTP client. Deliberate — see
  Risks.

## Design decisions to record

Two behaviour changes fall out of this and should not be smuggled in as implementation
details. Step 1 writes them up as a decision doc.

**1. Uncategorised spend starts counting toward surplus.** Today
`close_month` does `spent = sum(expenses.values())` over *categorised* buckets only
(`monthly_budget_service.py:300`), so an uncategorised expense silently inflates surplus
even without the truncation bug. Analytics' `/overview` returns `total_expenses` — the
canonical total, uncategorised included. Using it makes surplus correct, and is a real
semantic change: surpluses will drop on accounts with uncategorised rows, and goal
allocations shrink accordingly. That is the point, but it will look like a regression to
anyone who does not know why.

Per-line summary keeps using the per-category buckets, since a budget line is keyed on a
real `category_id` and the `None` bucket has no line to attach to. So the two call sites
deliberately consume **different fields of the same response** rather than sharing one
dict — `total_expenses` for surplus, `expenses_by_category` for lines. This is a split the
current code does not make, and it is why the port grows a second method rather than
changing the first one's return type.

**2. Spend becomes eventually consistent.** budget-service moves from a write-side
dependency (transaction-service's DB) to a read-side one (ES, event-synced). A close
executed seconds after an import could observe a not-yet-projected transaction. Assessed as
acceptable: the day-7 scheduler closes the *previous* month, so the projection has had days
to settle; the manual button is the only exposed race, and it is bounded by projection lag
(sub-second in practice). The dashboard already reads these numbers, so budget and overview
will now agree *because* they share a staleness rather than disagreeing on substance.

## Steps

1. [ ] **`docs(dev-notes): decision — budget-service reads spend from analytics`**
   New `dev-notes/decisions/2026-07-25-budget-spend-from-analytics.md` recording the two
   changes above with their trade-offs, so neither is rediscovered as a bug later.

2. [ ] **`refactor(budget): ISpendPort replaces ITransactionPort`**
   `app/application/ports/outbound.py:89-99` — rename the ABC and give it two methods:
   ```python
   class ISpendPort(ABC):
       async def get_expenses_by_category(...) -> dict[int, float]: ...
       async def get_total_expenses(...) -> Decimal: ...
   ```
   Same signature args (`account_id`, `start_date`, `end_date`, `user_id`), same
   `UpstreamServiceUnavailable` contract in the docstring. Pure rename + widening; no
   adapter or call site behaviour yet. Update the fake in `tests/unit` to match — existing
   tests must stay green on the old adapter.

3. [ ] **`feat(budget): analytics spend adapter`**
   New `app/adapters/outbound/analytics_port.py` implementing `ISpendPort` against
   `GET {ANALYTICS_SERVICE_URL}/api/v1/analytics/overview?account_id=&start_date=&end_date=`.
   Both methods hit the same endpoint and read different fields:
   `expenses_by_category[]` (skipping the `category_id: null` bucket, which has no line) and
   `total_expenses`. Reuse `make_service_auth_header(user_id)` unchanged — analytics runs on
   the same `JWT_SECRET` and the same `get_current_user_id` dependency, so the existing
   forged-user-token approach works as-is (still slated for replacement by P3-02).
   `ANALYTICS_SERVICE_URL: str = "http://localhost:8006"` into `app/config.py`.
   Non-200 and `httpx.HTTPError` → `UpstreamServiceUnavailable("analytics-service")`, so
   the existing fail-open/fail-closed branches keep working untouched.
   New unit tests with a stubbed transport: happy path, the `null`-category bucket is
   excluded from per-category but *included* in the total, 503 → `UpstreamServiceUnavailable`.

4. [ ] **`feat(budget): wire the three spend call sites to analytics`**
   `app/application/monthly_budget_service.py` — swap the injected port at composition root,
   then:
   - `:94` (`get_summary`) → `get_expenses_by_category`, unchanged fail-open `except`.
   - `:292-300` (`close_month`) → `get_total_expenses`, replacing
     `sum(Decimal(str(v)) for v in expenses.values())`. Fail-closed path unchanged.
   - `:349` (`evaluate_line_crossings`) → `get_expenses_by_category`, unchanged.
   Existing service tests should pass with only the fake updated — if any assert on a
   *number* rather than on the port being called, that is the uncategorised change from
   decision 1 showing up, and it needs an explicit test update, not a quiet one.

5. [ ] **`chore(budget): wire ANALYTICS_SERVICE_URL into all four containers`**
   `docker-compose.yml` — `budget-service` (:586), `budget-month-close-scheduler` (:635),
   `budget-alert-scheduler` (:660) all need `ANALYTICS_SERVICE_URL:
   http://analytics-service:8000`. `budget-outbox-worker` (:613) does not make spend calls;
   drop its now-unused `TRANSACTION_SERVICE_URL` rather than adding a second unused var.
   Add `analytics-service` to the two schedulers' `depends_on` (they currently wait only on
   `budget-service` + `rabbitmq`).
   **Per-worker build gotcha applies**: `compose build budget-service` does *not* rebuild
   the three sibling containers. Build them by name and grep the running container for the
   new adapter before trusting any live measurement.
   k8s manifests are covered by P2-21's drift work — note the new var there rather than
   fixing k8s piecemeal here.

6. [ ] **`chore(budget): delete the truncating transaction port`**
   Remove `app/adapters/outbound/transaction_port.py` and `TRANSACTION_SERVICE_URL` from
   `app/config.py`. Deliberately last: keeping it until the new path is verified means
   step 4 is revertible by swapping one injection.

7. [ ] **Verification**
   - `make -C services/budget-service test` (unit + integration), `make -C services/budget-service check`.
   - `make -C services/analytics-service test` — untouched, but it owns the contract now.
   - **The before/after measurement**, which is the actual proof. Baseline is recorded in
     the finding (account 1: June 94 tx → 5 180,32 of 16 739,83; July 61 tx → 10 286,17 of
     17 528,17). Expected after:

     | Period | Before | After | Postgres truth |
     |---|---|---|---|
     | June 2026 | 5 180,32 | **16 739,83** | 16 739,83 |
     | July 2026 | 10 286,17 | **17 666,17** | 17 528,17 |

     Both figures were confirmed against the running analytics-service *before* writing the
     adapter, so the target numbers are measured rather than predicted.

     **July will not match Postgres, and that is expected.** The 138,00 gap is phantom
     transaction 1119, left in `transactions_v2` by `cleanup_pg_duplicates.py` deleting
     behind the outbox → [P3-20](../findings/2026-07-25-cleanup-script-desyncs-read-model.md).
     Do not "fix" it inside this plan; a verification that demands 17 528,17 is asserting
     against a defect in a different component. June, which has no phantom, matches exactly
     — that is the clean proof.
   - Cross-check the same period against `GET /api/v1/analytics/overview` — budget and
     overview must now agree exactly, which is the Forbrug-vs-budget discrepancy closing.
   - **Mutation-check the fix**: temporarily re-point the adapter at transaction-service and
     confirm the summary drops back to 5 180,32. A test that cannot tell the two apart is
     not testing this.
   - **Fail-closed still holds**: stop analytics-service, confirm `close_month` 503s and does
     *not* close the month or emit an event, while `get_summary` still renders with
     `spent=0`.
   - **F2-03 end to end**: with real spend, account 1's July lines should cross thresholds
     they previously could not. Confirm the alert scheduler emits and that
     notification-service's `source_key` dedup still collapses re-emits across ticks.
   - Clean up any dev-DB artefacts the live run creates, per today's loose-ends session.

## Risks & rollback

**Surpluses shrink, and it will look like a bug.** Both fixes push spend up, so every
future close allocates less to goals — correctly. Already-closed months are *not*
recomputed and keep their historical (too-high) surplus; goal `amount_saved` values
allocated from those are not retro-corrected. Detection: the first close after deploy will
show a visibly smaller surplus. This is expected and is why decision 1 is written down.

**Eventual consistency on the manual close button.** Bounded by projection lag; the
scheduler path is unaffected. If it ever bites, the fix is a freshness check before close,
not a return to the write-side read.

**Analytics becomes a hard dependency of closing a month.** Today an analytics outage
degrades the dashboard; after this it also blocks month-close. That is the correct
trade-off given fail-closed is deliberate — a blocked close is recoverable, a wrong surplus
is not — but it widens the blast radius of an ES outage. The alert scheduler already skips
and retries next tick.

**Fourth hand-rolled HTTP client.** This adapter duplicates connection handling and error
taxonomy for the fourth time (notification, goal, banking, now budget), making P2-24 more
valuable and slightly more expensive. Accepted: blocking a money-correctness fix on a
cross-service refactor is the wrong order. Note it on P2-24 so the consolidation knows to
include this one.

**Rollback**: steps 2-4 are behind one injected port. Reverting = re-point the composition
root at `TransactionPort`, which is why step 6 deletes it only after verification. Steps 1
and 5 are inert on their own.
