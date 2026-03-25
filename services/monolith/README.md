# Finance Tracker Backend (Monolith)

FastAPI monolith for personal finance tracking with hexagonal architecture, GraphQL read gateway, event-driven sync, and structured logging.

**This is the monolith component.** User authentication, transaction management, and category ownership have been extracted into standalone microservices. The monolith still handles accounts, budgets, goals, and analytics. It receives events via RabbitMQ to keep local user and category caches synchronized.

## Quick Start

### Prerequisites

- Python 3.11+
- `uv`
- Docker (for MySQL, PostgreSQL, RabbitMQ)

### Install and run

```bash
# Start infrastructure (from repo root)
make dev

# Install dependencies and run monolith
make install-deps
make dev

# Run consumers (in separate terminals)
uv run python -m backend.consumers.worker --consumer user-sync
uv run python -m backend.consumers.worker --consumer account-creation
uv run python -m backend.consumers.worker --consumer category-sync
```

API base URL: `http://localhost:8000/api/v1/`

Health check:

```bash
curl http://localhost:8000/health
```

GraphQL playground: `http://localhost:8000/api/v1/graphql`

## Architecture

The monolith follows hexagonal (ports and adapters) architecture with CQRS:

1. **REST** handles commands (create, update, delete) via inbound adapters.
2. **GraphQL** handles read queries via a cross-domain read gateway.
3. Application services enforce business rules.
4. Outbound ports call database adapters (MySQL, Elasticsearch, Neo4j).
5. **Auth boundary** uses `IAccountResolver` port — `auth.py` has no direct repository imports.
6. **Unit of Work** pattern manages transaction boundaries in the Transaction domain.
7. **Shared infrastructure** in `backend/shared/` provides cross-cutting ports and adapters.
8. **Event consumers** sync user data and create default accounts via RabbitMQ.

Architecture boundaries are enforced by fitness tests in `tests/architecture/test_import_boundaries.py`.

See `docs/STRUCTURE.md` for the full structure map.

### Active domains (still in monolith)

- `transaction` — CRUD + CSV import (also available via transaction-service on port 8002)
- `budget` — legacy per-category budget CRUD + summary analytics
- `monthly_budget` — aggregate-based monthly budgets with budget lines, summary, and copy
- `analytics` — dashboard overview, expenses-by-month, budget summary, GraphQL read gateway
- `category` — CRUD (local cache, transaction-service on port 8002 is source of truth)
- `account` — CRUD + account groups
- `goal` — CRUD
- `user` — local user management (user-service on port 8001 is source of truth)

### Event consumers

| Consumer | Queue | Trigger | Action |
|----------|-------|---------|--------|
| `UserSyncConsumer` | `monolith.user_sync` | `user.created` | Insert user into MySQL |
| `AccountCreationConsumer` | `monolith.account_creation` | `user.created` | Create default account |
| `CategorySyncConsumer` | `monolith.category_sync` | `category.*` | Sync categories from transaction-service |

All consumers run independently with retry (3 attempts), DLQ, and DB-backed idempotency (`processed_events` table with auto-cleanup after 7 days).

### Router map (all under `/api/v1/`)

| Path | Domain | Protocol |
|------|--------|----------|
| `/api/v1/transactions/*` | Transaction | REST |
| `/api/v1/planned-transactions/*` | Transaction | REST |
| `/api/v1/categories/*` | Category | REST |
| `/api/v1/budgets/*` | Budget (legacy) | REST |
| `/api/v1/monthly-budgets/*` | Monthly Budget | REST |
| `/api/v1/dashboard/*` | Analytics | REST |
| `/api/v1/accounts/*` | Account | REST |
| `/api/v1/account-groups/*` | Account | REST |
| `/api/v1/goals/*` | Goal | REST |
| `/api/v1/users/*` | User | REST |
| `/api/v1/graphql` | Analytics (read gateway) | GraphQL |

## Configuration

All config is loaded from `backend/config.py` via environment variables.

| Variable | Purpose | Default |
|----------|---------|---------|
| `DATABASE_URL` | MySQL connection string | — |
| `SECRET_KEY` | JWT signing key (must match across services) | — |
| `RABBITMQ_URL` | RabbitMQ connection string | `amqp://guest:guest@localhost:5672/` |
| `CORS_ORIGINS` | Allowed frontend origins | `http://localhost:3000,http://localhost:3001` |
| `ACTIVE_DB` | Global fallback DB | `mysql` |
| `ENVIRONMENT` | Runtime environment | `development` |
| `LOG_LEVEL` | Logging level | `INFO` |

See `example.env` for the full list with descriptions.

## Commands

```bash
# All tests via Makefile
make test

# Unit tests only
make test-unit

# Integration tests only
make test-integration

# Lint + format check
make check

# Run specific consumer
uv run python -m backend.consumers.worker --consumer user-sync
uv run python -m backend.consumers.worker --consumer account-creation
uv run python -m backend.consumers.worker --consumer category-sync

# Run all consumers
uv run python -m backend.consumers.worker
```
