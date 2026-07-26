---
title: The transactions page silently shows only the 50 newest rows in the selected period
date: 2026-07-26
severity: HIGH
area: frontend, transaction
status: open
resolved-by: null
---

# The transactions page silently shows only the 50 newest rows in the selected period

**Where**: `services/frontend/src/api/transactions.jsx:24-31` (client) against
`services/transaction-service/app/adapters/inbound/rest_api.py:61` (server).

**Defect**: `fetchTransactions` builds a param object containing only `start_date`,
`end_date` and `category_id` — it never sends `limit` or `skip`. The server signature is
`skip: int = 0, limit: int = 50`, and the repository applies it in SQL *after*
`ORDER BY date DESC, id DESC` (`postgres_transaction_repository.py:91`). The UI then maps
the whole returned array into a `<table>` with no pagination, no "load more", no total
count and no truncation notice (`components/TransactionsList/TransactionsList.jsx:80`).

This is the **same defect mechanism as [P1-13](2026-07-25-budget-spend-truncated-at-50.md)**:
a client that omits `limit`, meeting a 50-row server default that is applied after a
date-descending sort. P1-13 fixed the budget-service call site. This is the call site the
user actually looks at, and it was not part of that fix.

## Measured (2026-07-26, running dev stack, user_id 1 / account 1)

```sql
select account_id, to_char(date,'YYYY-MM') as month, count(*)
from transactions where user_id=1 group by 1,2 order by 2 desc;
```

| Month | Rows in Postgres | Rows the page can show | Hidden |
|---|---|---|---|
| 2026-07 | 61 | 50 | 11 (18%) |
| 2026-06 | 93 | 50 | **43 (46%)** |
| 2026-05 | 53 | 50 | 3 |
| 2026-04 | 50 | 50 | 0 — exactly at the ceiling |

**Why it matters**: because the truncation is applied after `date DESC`, the rows that
disappear are the *oldest ones in the period*. Selecting June 2026 shows June 30 back to
roughly June 16 and silently drops the first half of the month. There is nothing in the UI
that distinguishes this from "that is all there was".

The damage compounds with P1-13 rather than being mitigated by it. Since 2026-07-25 the
dashboard reads spend from analytics and reports June correctly as 16 739,83 across 93
transactions. The transactions page still lists 50 of those 93. **The user now sees a
correct total that cannot be reconciled against the list underneath it**, and the natural
reading is that the total is wrong — the opposite of the trust P1-13 bought.

April sitting exactly on 50 is worth noting separately: that account-month is one
transaction away from starting to lose rows with no visible change in behaviour.

## Related, same file, separate ceiling

Free-text search hardcodes `limit: 100` (`hooks/useTransactionSearch.jsx:59`) and renders
"X af Y resultater" (`pages/TransactionsPage.jsx:195-199`) — so a search matching 400 rows
displays "100 af 400" and offers no way to reach the remaining 300. Here the count is at
least honest; the navigation is still missing.

Search also ignores the active date/category filters: `useTransactionSearch` is called
without the `filters` argument (`TransactionsPage.jsx:74`) although the hook accepts it,
while the filter panel stays visually active.

## Suggested fix

Not `&limit=10000` — that is the shortcut P1-13's decision record explicitly rejected, and
it moves the cliff instead of removing it.

1. Thread `skip`/`limit` through `fetchTransactions` → `crudFactory.fetchAll`, and return
   a total so the UI can render "viser 50 af 93".
   The server needs to return that total; today the endpoint returns a bare
   `list[TransactionResponse]` with no envelope, so this is a response-shape change
   (`rest_api.py:51`) and needs a decision on whether to version it or add a
   `X-Total-Count` header.
2. Page the UI (server-side paging is enough — virtualisation is a separate concern and
   only matters once a single page is large).
3. Apply the same treatment to the search path.

**Scope note**: P3-06 already lists "pagination/virtualized tx table" as one clause in a
frontend-hygiene item. That classification is wrong for the pagination half — a UI that
presents an incomplete set of financial records as if it were complete is a correctness
defect, not hygiene. Filed as P1-14; the virtualisation clause can stay in P3-06.

## Verification when fixed

June 2026 for account 1 must be reachable in full: 93 rows across pages, and the sum of
the listed amounts must reconcile with the 16 739,83 analytics reports for the same period.
