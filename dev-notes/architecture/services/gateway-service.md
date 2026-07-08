---
title: gateway-service (BFF) + analytics/notification stubs + monolith footprint
updated: 2026-07-07
source: architecture audit 2026-07-07
---

# gateway-service (port 8010)

Read-only BFF. Three inbound surfaces under `/api/v1` (`app/main.py:38-40`):

1. **REST dashboard** — `adapters/inbound/rest_api.py`: `/dashboard/overview/`, `/dashboard/expenses-by-month/`.
2. **GraphQL (Strawberry)** — `adapters/inbound/graphql_api.py`: query-only root with 9 fields (`financialOverview`, `expensesByMonth`, `budgetSummary`, `currentMonthOverview`, `topSpendingCategories`, `categories`, `subcategories`, `transactions`). No mutations/subscriptions.
3. **Saga status** — `adapters/inbound/saga_api.py`: `GET /sagas/{id}` proxied to saga-service with gateway-side ownership check (the *model* error-handling code in this service).

Layering: hexagonal-lite. Real aggregation logic lives in `app/application/service.py` (`AnalyticsService` — misleading name given the separate analytics-service stub; think `DashboardReadService`). 5 outbound HTTP clients (transaction, categorization, account, budget, saga) — all **sync `httpx.Client`, new client per call**, per-service timeouts, no retries/circuit breakers/caching.

Auth: JWT validated locally (own copy of `app/auth.py`, one of 9 near-identical copies repo-wide); raw `Authorization` passed through downstream. Account scoping via `X-Account-ID`, ownership verified by a live HTTP call to account-service **per request**; missing header falls back to "first account in list" heuristic.

## Read flow (as-built, worst case: GraphQL `currentMonthOverview`)

```
ownership check (HTTP) → budget_start_day (HTTP) →
financial_overview(current)  = full tx history (HTTP, NO date/limit params!) + all categories (HTTP)
financial_overview(previous) = full tx history AGAIN + categories AGAIN
```
5–6 **sequential** round trips; there is no parallel fan-out anywhere despite the BFF role. Multi-field GraphQL queries multiply this — 4 dashboard fields ⇒ 4 independent full-history downloads in one request (only `_budget_start_day_cache` is memoized per request).

## Stubs & monolith

- `analytics-service`, `notification-service`: honest stubs (health endpoint only), commented out of compose.
- `services/monolith/`: **0 git-tracked files** — the ~9.2k local files are untracked debris (.venv, 273 orphaned .pyc). Safe to delete locally.

## Open problems

See [findings/2026-07-07-architecture-audit.md](../../findings/2026-07-07-architecture-audit.md). Headliners: unbounded full-history fetch on every read (CRITICAL), empty-string JWT secret fallback fails open (CRITICAL), sync HTTP + no pooling saturates threadpool (HIGH), no per-request memoization of the expensive fetch (HIGH), `budget_period.py` triplicated byte-for-byte across gateway/budget/account services (MEDIUM).
