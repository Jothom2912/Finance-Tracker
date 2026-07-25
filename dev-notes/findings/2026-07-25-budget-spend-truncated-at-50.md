---
title: budget-service computes spend from at most 50 transactions
date: 2026-07-25
severity: HIGH
area: budget, transaction
status: resolved
resolved-by: ../plans/2026-07-25-p113-budget-spend-from-analytics.md
---

# budget-service computes spend from at most 50 transactions

**Where**: `services/budget-service/app/adapters/outbound/transaction_port.py:26-31`
(the request), against `services/transaction-service/app/adapters/inbound/rest_api.py:61`
(the default) and `services/transaction-service/app/adapters/outbound/postgres_transaction_repository.py:91`
(the SQL).

**Defect**: `TransactionPort.get_expenses_by_category` builds its URL with `account_id`,
`start_date` and `end_date` but **no `limit`**:

```python
url = (
    f"{settings.TRANSACTION_SERVICE_URL}/api/v1/transactions"
    f"?account_id={account_id}"
    f"&start_date={start_date.isoformat()}"
    f"&end_date={end_date.isoformat()}"
)
```

transaction-service's list endpoint defaults to `limit: int = 50`, and the repository
applies it in SQL after `order_by(date DESC, id DESC)`. Budget-service therefore sums the
**50 most recent** transactions in the period and silently treats that as the whole month.

The port has two further divergences from the canonical rules in the same loop:
`category_id is None` is skipped (line 49-50) and only `transaction_type == "expense"`
counts (line 52-53), so uncategorised rows and legacy rows without a type are invisible
too. The truncation is the dominant one.

**Why it matters**: The port feeds three call sites in
`services/budget-service/app/application/monthly_budget_service.py`:

| Line | Caller | Effect of truncation |
|---|---|---|
| 94 | budget summary (the "Budget-overholdelse" widget) | spend displayed too low |
| 292 | **`close_month`** | `spent` too low → **surplus too high → over-allocation to the user's goal** |
| 349 | **F2-03 alert evaluation** | 80%/100% thresholds never cross on busy categories |

Measured in the dev database on 2026-07-25, account 1:

| Period | Tx in window | Seen by budget-service | True spend | Computed spend | Understated by |
|---|---|---|---|---|---|
| June 2026 | 94 | 50 | 16 739,83 | 5 180,32 | **11 559,51 (69%)** |
| July 2026 | 61 | 50 | 17 528,17 | 10 286,17 | **7 242,00 (41%)** |

July 2026 is `monthly_budgets.id=9`, currently **open** — so the budget-alert-scheduler is
evaluating live thresholds against 59% of real spend right now, and closing that month
today would credit a ~7 200 kr surplus that does not exist to whatever goal is default.

Four account-months in the dev DB already exceed the limit. Sixty-plus transactions a month
is an ordinary account, not a stress case; the bug is invisible precisely on the small test
accounts that the e2e work has used so far.

`close_month` is explicitly fail-closed against exactly this failure mode — the comment at
`monthly_budget_service.py:288-291` says a `spent=0` fallback "ville kreditere et fiktivt
overskud til mål" and therefore propagates `UpstreamServiceUnavailable` rather than
degrading. The truncation produces the same fictional surplus, just partially and without
raising anything, so the guard never fires.

This also explains the residual half of the long-tracked "Forbrug vs. budget"
discrepancy: the gateway/dashboard side reads from analytics (ES, unbounded) while the
budget widget reads 50 rows. The two numbers *cannot* agree.

**Suggested fix**: Do **not** just append `&limit=10000` — that trades a silent wrong
answer for a silent ceiling, and leaves the type/uncategorised divergences in place.

Point budget-service at analytics-service instead. The canonical aggregation rules already
live in `services/analytics-service/app/domain/` (`classification.py` + `budget_period.py`)
and are the documented owner of "what counts as spend" per
[ADR-0004](../../docs/adr/0004-analytics-elasticsearch-read-store.md). That removes all
three divergences at once and leaves one implementation of the rules instead of two.

Trade-off to accept: budget-service moves from a write-side dependency (transaction-service)
to a read-side one (analytics/ES), so spend becomes eventually consistent. That is already
the dashboard's reality, and the alternative is maintaining aggregation rules in two places
— which is what produced the divergence in the first place. `close_month` must keep its
fail-closed behaviour against the new upstream.

Tracked as P1-13 — **resolved 2026-07-25** by
[the plan](../plans/2026-07-25-p113-budget-spend-from-analytics.md). budget-service now reads
spend from analytics; June went 5 180,32 → 16 739,83 (matching Postgres exactly) and July
10 286,17 → 17 666,17. The residual 138,00 on July is a phantom row from a different defect
([P3-20](2026-07-25-cleanup-script-desyncs-read-model.md)), not this one.
