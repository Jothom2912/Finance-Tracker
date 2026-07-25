---
title: budget-service reads spend from analytics, and uncategorised spend counts toward surplus
date: 2026-07-25
status: accepted
supersedes: null
promoted-to-adr: null
---

# budget-service reads spend from analytics, and uncategorised spend counts toward surplus

## Decision

budget-service stops computing spend itself from transaction-service's list endpoint and
reads it from analytics-service's `/api/v1/analytics/overview`, the documented owner of the
canonical aggregation rules ([ADR-0004](../../docs/adr/0004-analytics-elasticsearch-read-store.md)).

Two behaviour changes follow, both accepted deliberately rather than as side effects:

1. **Uncategorised expenses now count toward the month-close surplus.**
2. **Spend becomes eventually consistent** (read-side dependency instead of write-side).

## Context

[P1-13](../findings/2026-07-25-budget-spend-truncated-at-50.md): `TransactionPort` sent no
`limit`, so transaction-service's default of 50 applied and budget-service summed the 50
newest rows of a period and treated that as the month. Measured on the dev DB: account 1,
June 2026 → 94 transactions, true spend 16 739,83, computed 5 180,32 — **69% understated**.
That number feeds the budget widget, F2-03's alert thresholds, and `close_month`'s surplus,
which is allocated to the user's savings goal.

Fixing only the truncation (`&limit=10000`) would have left two smaller divergences in the
same twenty-line loop: `category_id is None` was skipped, and only
`transaction_type == "expense"` counted, so legacy rows without a type were dropped.
analytics already implements the canonical rule for both — `is_expense()` in
`services/analytics-service/app/domain/classification.py:26-27` falls back to the amount's
sign for typeless rows, and `CategoryExpenseDTO` buckets uncategorised as
`category_id: None`. So the choice was not "fix the limit" versus "adopt analytics" but
"maintain the rules in two places" versus "one".

The uncategorised question forced itself once analytics was on the table. `close_month`
computes `spent = sum(expenses.values())` over categorised buckets only
(`monthly_budget_service.py:300`), so an uncategorised expense inflated the surplus *even
without* the truncation bug. analytics returns `total_expenses`, which includes it. Keeping
the old behaviour would have meant deliberately reconstructing a known-wrong total from a
correct response.

## Alternatives considered

- **`&limit=10000` on the existing call** — rejected. Trades a silent wrong answer for a
  silent ceiling that reappears at a different account size, and leaves the type and
  uncategorised divergences in place. Cheapest to write, most expensive to trust.
- **Paginate transaction-service properly from budget-service** — rejected. Correct on the
  truncation, but it makes budget-service a second implementation of the aggregation rules,
  which is exactly the condition that produced the long-tracked Forbrug-vs-budget
  discrepancy. More code for a worse architecture.
- **Add a dedicated spend endpoint to analytics** — rejected as unnecessary. `/overview`
  already returns `total_expenses` and `expenses_by_category` with `category_id`, for an
  arbitrary `start_date`/`end_date`. A new endpoint would be a thinner projection of a
  response we already have to fetch.
- **Keep uncategorised out of the surplus** — rejected. It would require filtering a
  correct total back down to a known-wrong one. If uncategorised spend should be excluded
  from goal allocation that is a product decision about *categorisation coverage*, not
  something to encode by quietly under-counting money the user actually spent.
- **Emit spend from transaction-service as an event** — not considered seriously for this
  fix; it is a larger design (a spend read-model per account-period) and P1-13 is a
  money-correctness bug that should not wait on it.

## Consequences

**Surpluses shrink, and closed months are not recomputed.** Both changes push spend up, so
every future close allocates less to goals — correctly. Historical closed months keep their
too-high `surplus_amount`, and goal `amount_saved` values already credited from them are
not retro-corrected. The first close after deploy will look like a regression to anyone who
does not know why; that is the main reason this document exists.

**Analytics becomes a hard dependency of closing a month.** Today an analytics outage
degrades the dashboard; after this it also blocks month-close, because `close_month` is
fail-closed by design and that policy is preserved against the new upstream. Accepted: a
blocked close is recoverable, a wrong surplus is not. The alert scheduler already skips and
retries on the next tick, and `get_summary` keeps its fail-open `spent=0` degradation.

**Budget and dashboard now share a staleness instead of disagreeing on substance.** The
manual close button is the only path meaningfully exposed to projection lag — the day-7
scheduler closes the *previous* month, by which time the projection has had days to settle.
If lag ever bites, the fix is a freshness check before closing, not a return to reading the
write side.

**One more hand-rolled internal HTTP client.** This is the fourth (notification, goal,
banking, now budget), which makes [P2-24](../backlog/BACKLOG.md) more valuable and slightly
more expensive. Accepted ordering: a money-correctness fix should not block on a
cross-service refactor.

**Unblocks** the remaining half of the Forbrug-vs-budget discrepancy — after this, the
budget widget and the overview read the same numbers from the same source, so they can be
asserted equal in a test rather than explained away.
