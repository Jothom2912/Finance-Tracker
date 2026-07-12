---
title: gateway-service (BFF) + monolith footprint
updated: 2026-07-13
source: architecture audit 2026-07-07; ADR-0004 cutover + legacy-path deletion 2026-07-13
---

# gateway-service (port 8010)

Read-only BFF. Two inbound surfaces under `/api/v1` (`app/main.py`):

1. **GraphQL (Strawberry)** — `adapters/inbound/graphql_api.py`: query-only root
   (`financialOverview`, `expensesByMonth`, `budgetSummary`, `periodOverview`,
   `currentMonthOverview`, `cashflowByMonth`, `monthComparison`, `searchTransactions`,
   `topSpendingCategories`, `categories`, `subcategories`, `transactions`).
   No mutations/subscriptions.
2. **Saga status** — `adapters/inbound/saga_api.py`: `GET /sagas/{id}` proxied to
   saga-service with gateway-side ownership check.

**REST `/dashboard/*` er slettet (2026-07-13)** sammen med hele legacy-read-stien:
`AnalyticsService`-aggregeringen, `HttpAnalyticsReadRepository` (transaction-service
pagineret fuldhistorik-fetch), `LegacyFinancialAnalyticsAdapter`,
`DualReadFinancialAnalyticsRepository` og `ANALYTICS_READ_SOURCE`-flaget.
Se ADR-0004 §Oprydning. Gatewayen kalder ikke længere transaction-service.

## Read-side (as-built efter ADR-0004)

Alle finansielle reads går gennem `HttpFinancialAnalyticsRepository`
(`adapters/outbound/analytics_client.py`) → analytics-service `/api/v1/analytics/*`
(ES-backed, præ-aggregeret). Én instans pr. request implementerer begge porte
(`IFinancialAnalyticsPort` + `IAnalyticsInsightsPort` i `application/ports/outbound.py`);
resolvers afhænger af den smalle port. 503/transportfejl mappes til
`AnalyticsServiceUnavailable` med dansk besked.

Øvrige outbound-klienter: account (budget_start_day + ownership), budget (summary),
categorization (taxonomy, ADR-003), saga. Alle sync `httpx.Client`, ny klient per kald
— acceptabelt nu hvor de tunge aggregeringskald er væk (P2-04's async-omskrivning blev
bevidst rullet tilbage; genovervej kun hvis latency-målinger kræver det).

Per-request caches i GraphQL-konteksten: `_budget_start_day_cache` (den tidligere
transaktions-memoization røg med legacy-stien — ES-kaldene er billige og præ-aggregerede).

Auth: JWT validated locally (own copy of `app/auth.py`, one of 9 near-identical copies
repo-wide — P2-02 adoption pending); raw `Authorization` passed through downstream.
Account scoping via `X-Account-ID`, ownership verified via account-service per request;
missing header falls back to "first account in list" heuristic.

## Stubs & monolith

- `notification-service`: honest stub (health endpoint only), commented out of compose.
- `services/monolith/`: 0 git-tracked files — local debris only, safe to delete locally.

## Open problems

See [findings/2026-07-07-architecture-audit.md](../../findings/2026-07-07-architecture-audit.md)
— men bemærk at hele klassen "unbounded full-history fetch on every read" (CRITICAL) og
"no per-request memoization" (HIGH) er **bortfaldet** med legacy-stien. Tilbage:
sync HTTP uden pooling (lav impact nu), `budget_period.py`-triplikering (P2-03 adoption),
auth-kopi (P2-02 adoption), P3-12 (GraphiQL-gating, depth limits, 401-semantik).
