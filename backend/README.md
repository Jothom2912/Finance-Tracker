# Finance Tracker Backend

FastAPI backend for personal finance tracking with hexagonal architecture, GraphQL read gateway, and structured logging.

## Quick Start

### Prerequisites

- Python 3.11+
- `uv`
- Docker (optional, for local database services)

### Install and run

```bash
cd backend
uv sync
uv run uvicorn backend.main:app --reload --port 8000
```

API base URL: `http://localhost:8000/api/v1/`

Health check (not versioned):

```bash
curl http://localhost:8000/health
```

GraphQL playground: `http://localhost:8000/api/v1/graphql`

## Architecture

The runtime follows a hexagonal (ports and adapters) structure with CQRS:

1. **REST** handles commands (create, update, delete) via inbound adapters.
2. **GraphQL** handles read queries via a cross-domain read gateway.
3. Application services enforce business rules.
4. Outbound ports call database adapters (MySQL, Elasticsearch, Neo4j).

See `backend/docs/STRUCTURE.md` for the full structure map.

### Active domains

- `transaction` -- CRUD + CSV import
- `budget` -- CRUD + summary analytics
- `analytics` -- dashboard overview, expenses-by-month, budget summary, GraphQL read gateway
- `category` -- CRUD
- `account` -- CRUD + account groups
- `goal` -- CRUD
- `user` -- registration, login, JWT auth

### Router map (all under `/api/v1/`)

| Path | Domain | Protocol |
|---|---|---|
| `/api/v1/transactions/*` | Transaction | REST |
| `/api/v1/planned-transactions/*` | Transaction | REST |
| `/api/v1/categories/*` | Category | REST |
| `/api/v1/budgets/*` | Budget | REST |
| `/api/v1/budgets/summary` | Analytics | REST |
| `/api/v1/dashboard/overview/` | Analytics | REST |
| `/api/v1/dashboard/expenses-by-month/` | Analytics | REST |
| `/api/v1/accounts/*` | Account | REST |
| `/api/v1/account-groups/*` | Account | REST |
| `/api/v1/goals/*` | Goal | REST |
| `/api/v1/users/*` | User | REST |
| `/api/v1/graphql` | Analytics (read gateway) | GraphQL |

### GraphQL read gateway

The GraphQL endpoint at `/api/v1/graphql` is a cross-domain read gateway that aggregates data from multiple bounded contexts through a single query interface. This is a deliberate CQRS pattern: REST handles writes, GraphQL handles reads.

Available queries: `financialOverview`, `expensesByMonth`, `budgetSummary`, `categories`, `transactions`.

No mutations are exposed -- all write operations use REST endpoints.

## Configuration

All config is loaded from `backend/config.py` via environment variables.

### Core variables

| Variable | Purpose | Default |
|---|---|---|
| `ACTIVE_DB` | Global fallback DB | `mysql` |
| `TRANSACTIONS_DB` | DB role for transaction workloads | `mysql` |
| `ANALYTICS_DB` | DB role for analytics workloads | `ACTIVE_DB` |
| `USER_DB` | DB role for user workloads | `mysql` |
| `DATABASE_URL` | MySQL connection string | - |
| `SECRET_KEY` | JWT signing key (required) | - |
| `CORS_ORIGINS` | Allowed frontend origins | `http://localhost:3000,http://localhost:3001` |
| `ENVIRONMENT` | `development`, `staging`, `production` | `development` |
| `LOG_LEVEL` | Logging level (`DEBUG`, `INFO`, etc.) | `INFO` |

See `example.env` for the full list with descriptions.

### Logging and observability

- Every request gets a correlation ID (auto-generated UUID or forwarded from `X-Correlation-ID` header).
- The correlation ID is returned in the `X-Correlation-ID` response header for traceability.
- In `development` mode, logs use human-readable format.
- In other environments, logs output structured JSON with `correlation_id`, `method`, `path`, `status`, and `duration_ms`.

## Commands

Run all backend tests:

```bash
uv run pytest tests/ -v
```

Run integration tests only:

```bash
uv run pytest tests/integration
```

Run unit tests only:

```bash
uv run pytest tests/unittests
```
