# Backend Structure (Hexagonal)

## Overview

The backend runtime now follows a hexagonal architecture across all active endpoints.

Legacy runtime code in `backend/routes/` and legacy business services in
`backend/services/` were removed as part of the migration.

## Runtime Entry Points

- `backend/main.py` registers FastAPI routers.
- `backend/dependencies.py` wires application services with outbound adapters.

## Active Bounded Contexts

- `backend/transaction/`
- `backend/category/`
- `backend/budget/`
- `backend/analytics/`
- `backend/account/`
- `backend/goal/`
- `backend/user/`

Each context follows the same layout:

```text
<context>/
├── adapters/
│   ├── inbound/
│   └── outbound/
├── application/
│   ├── ports/
│   └── service.py
├── domain/
└── __init__.py
```

## Router Map

- `/transactions/*`
- `/planned-transactions/*`
- `/categories/*`
- `/budgets/*` (CRUD)
- `/budgets/summary`
- `/dashboard/overview/`
- `/dashboard/expenses-by-month/`
- `/accounts/*`
- `/account-groups/*`
- `/goals/*`
- `/users/*`

## Database Role Configuration

Database settings live in `backend/config.py`.

Key variables:

- `ACTIVE_DB` (global fallback)
- `TRANSACTIONS_DB`
- `ANALYTICS_DB`
- `USER_DB`

Current behavior:

- Transactional write paths use MySQL-backed adapters.
- Analytics reads are selected by `ANALYTICS_DB` (MySQL, Elasticsearch, Neo4j).

## Removed Legacy Runtime Files

- `backend/routes/accounts.py`
- `backend/routes/account_groups.py`
- `backend/routes/categories.py`
- `backend/routes/goals.py`
- `backend/routes/planned_transactions.py`
- `backend/routes/transactions.py`
- `backend/routes/users.py`
- `backend/routes/dashboard.py`
- `backend/routes/budgets.py`

## Removed Legacy Service Files

- `backend/services/account_service.py`
- `backend/services/budget_service.py`
- `backend/services/category_service.py`
- `backend/services/dashboard_service.py`
- `backend/services/goal_service.py`
- `backend/services/transaction_service.py`
- `backend/services/user_service.py`
