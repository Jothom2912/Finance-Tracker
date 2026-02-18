# Finance Tracker Backend

FastAPI backend for personal finance tracking.

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

API URL: `http://localhost:8000`

Health check:

```bash
curl http://localhost:8000/health
```

## Architecture

The runtime follows a hexagonal structure:

1. Inbound adapters receive HTTP requests.
2. Application services run business rules.
3. Outbound ports call database adapters.
4. Adapters return data to services and responses.

See `backend/docs/STRUCTURE.md` for the full structure map.

### Active domains

- `transaction`
- `budget`
- `analytics`
- `category`
- `account`
- `goal`
- `user`

### Router overview

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

## Database Configuration

Configuration is loaded from `backend/config.py`.

### Core variables

| Variable | Purpose | Default |
|---|---|---|
| `ACTIVE_DB` | Global fallback DB | `mysql` |
| `TRANSACTIONS_DB` | DB role for transaction workloads | `mysql` |
| `ANALYTICS_DB` | DB role for analytics workloads | `ACTIVE_DB` |
| `USER_DB` | DB role for user workloads | `mysql` |
| `DATABASE_URL` | MySQL connection string | - |
| `ELASTICSEARCH_HOST` | Elasticsearch endpoint | `http://localhost:9200` |
| `NEO4J_URI` | Neo4j bolt URI | `bolt://localhost:7687` |
| `NEO4J_USER` | Neo4j user | `neo4j` |
| `NEO4J_PASSWORD` | Neo4j password | `password` |
| `SECRET_KEY` | JWT signing key | - |
| `CORS_ORIGINS` | Allowed frontend origins | `http://localhost:3000,http://localhost:3001` |

### Analytics DB behavior

`ANALYTICS_DB` controls which adapter Analytics uses:

- `mysql` -> `analytics/adapters/outbound/mysql_repository.py`
- `elasticsearch` -> `analytics/adapters/outbound/elasticsearch_repository.py`
- `neo4j` -> `analytics/adapters/outbound/neo4j_repository.py`

## Commands

Run all backend tests:

```bash
uv run pytest backend/tests
```

Run integration tests only:

```bash
uv run pytest backend/tests/integration
```

Run unit tests only:

```bash
uv run pytest backend/tests/unittests
```
