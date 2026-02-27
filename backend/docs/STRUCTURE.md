# Backend Structure (Hexagonal + CQRS)

## Overview

The backend uses hexagonal architecture across all domains with a CQRS split:
- **REST** for commands (write operations)
- **GraphQL** for queries (read operations via a cross-domain read gateway)

All routes are versioned under `/api/v1/`. The `/health` and `/` endpoints remain at root.

## Runtime Entry Points

- `backend/main.py` -- registers routers, middleware (CORS, request logging, correlation ID), and the GraphQL endpoint.
- `backend/dependencies.py` -- wires application services with outbound adapters via FastAPI DI.

## Active Bounded Contexts

- `backend/transaction/`
- `backend/category/`
- `backend/budget/` -- legacy per-category budgets
- `backend/monthly_budget/` -- aggregate-based monthly budgets with budget lines
- `backend/analytics/` -- includes the GraphQL read gateway adapter
- `backend/account/`
- `backend/goal/`
- `backend/user/`

Each context follows the same layout:

```text
<context>/
├── adapters/
│   ├── inbound/       # REST API (+ GraphQL for analytics)
│   └── outbound/      # Repository implementations
├── application/
│   ├── ports/         # Inbound + outbound interfaces
│   ├── service.py     # Application service
│   └── dto.py         # Data transfer objects
├── domain/
│   ├── entities.py
│   └── exceptions.py
└── __init__.py
```

### Monthly Budget domain

The `monthly_budget` context replaces the legacy `budget` context with an aggregate-based model. Instead of one budget row per category, a `MonthlyBudget` aggregate groups multiple `BudgetLine` entries under a single month/year/account combination. It supports budget copying between months and provides its own summary endpoint that compares budget lines against actual transaction spending.

The legacy `budget` context remains for backward compatibility and is still used by the GraphQL `budgetSummary` query via `AnalyticsService`.

### Analytics domain -- read gateway

The `analytics` context contains an extra inbound adapter: `graphql_api.py`. This adapter is a cross-domain read gateway that injects services from other bounded contexts (transactions, categories) to serve read-only GraphQL queries. This is a deliberate architectural choice to provide a single query interface without breaking domain encapsulation -- each domain's service layer is the only entry point.

## Router Map

| Path | Domain | Protocol |
|---|---|---|
| `/api/v1/transactions/*` | Transaction | REST |
| `/api/v1/planned-transactions/*` | Transaction | REST |
| `/api/v1/categories/*` | Category | REST |
| `/api/v1/budgets/*` (CRUD) | Budget (legacy) | REST |
| `/api/v1/budgets/summary` | Analytics | REST |
| `/api/v1/monthly-budgets/*` (CRUD + copy) | Monthly Budget | REST |
| `/api/v1/monthly-budgets/summary` | Monthly Budget | REST |
| `/api/v1/dashboard/*` | Analytics | REST |
| `/api/v1/accounts/*` | Account | REST |
| `/api/v1/account-groups/*` | Account | REST |
| `/api/v1/goals/*` | Goal | REST |
| `/api/v1/users/*` | User | REST |
| `/api/v1/graphql` | Analytics (read gateway) | GraphQL |

## Middleware Stack

1. **CORS** -- configured via `CORS_ORIGINS` env var.
2. **Request Logging** -- logs method, path, status, duration_ms, and correlation_id.
3. **Correlation ID** -- generates UUID per request (or forwards `X-Correlation-ID` header). Returned in `X-Correlation-ID` response header.

## Database Role Configuration

Settings in `backend/config.py`:

- `ACTIVE_DB` -- global fallback
- `TRANSACTIONS_DB` -- transaction domain
- `ANALYTICS_DB` -- analytics domain (supports MySQL, Elasticsearch, Neo4j)
- `USER_DB` -- user domain

## Removed Legacy Files

All legacy `backend/routes/` and `backend/services/` files were removed during the hexagonal migration. The legacy `backend/graphql/` directory (direct SessionLocal access) was also removed and replaced by the hexagonal GraphQL read gateway in `backend/analytics/adapters/inbound/graphql_api.py`.
