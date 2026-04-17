# Finance Tracker Backend (Monolith)

FastAPI monolith for personal finance tracking with hexagonal architecture, GraphQL read gateway, event-driven sync, structured logging, live bank integration (PSD2 via Enable Banking), and multi-tier auto-categorization.

**This is the monolith component.** User authentication, transaction management, planned transactions and category ownership have been extracted into standalone microservices. The monolith handles accounts, budgets, goals, analytics, **bank connections**, and **transaction categorization**. It receives events via RabbitMQ to keep local user, category and transaction projections synchronized.

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

- `category` — three-level hierarchy (Category / SubCategory / Merchant) + categorization pipeline. Category write ownership lives in `transaction-service`; this domain reads the projected MySQL copy
- `banking` — PSD2 bank integration via Enable Banking (OAuth flow, transaction sync). Bank-synced transactions are forwarded to `transaction-service` via HTTP (`POST /api/v1/transactions/bulk`); deduplication and persistence happen there, and the MySQL projection is populated via events
- `budget` — legacy per-category budget CRUD + summary analytics
- `monthly_budget` — aggregate-based monthly budgets with budget lines, summary, and copy
- `analytics` — dashboard overview, expenses-by-month, budget summary, GraphQL read gateway. Reads the MySQL transaction projection populated by `TransactionSyncConsumer`
- `account` — CRUD + account groups
- `goal` — CRUD
- `user` — local user management (user-service on port 8001 is source of truth)

### Extracted domains (no longer in the monolith)

- `transaction` + `planned_transaction` — now fully owned by `transaction-service` (port 8002). The monolith keeps a read-only MySQL projection materialised from `transaction.*` events (see `TransactionSyncConsumer`)

### Event consumers

| Consumer | Queue | Trigger | Action |
|----------|-------|---------|--------|
| `UserSyncConsumer` | `monolith.user_sync` | `user.created` | Insert user into MySQL |
| `AccountCreationConsumer` | `monolith.account_creation` | `user.created` | Create default account |
| `CategorySyncConsumer` | `monolith.category_sync` | `category.*` | Sync categories from transaction-service |
| `TransactionSyncConsumer` | `monolith.transaction_sync` | `transaction.*` | Project transaction writes into MySQL read model |

All consumers run independently with retry (3 attempts), DLQ, and DB-backed idempotency (`processed_events` table with auto-cleanup after 7 days).

### Router map (all under `/api/v1/`)

| Path | Domain | Protocol |
|------|--------|----------|
| `/api/v1/bank/*` | Banking (PSD2) | REST |
| `/api/v1/budgets/*` | Budget (legacy) | REST |
| `/api/v1/monthly-budgets/*` | Monthly Budget | REST |
| `/api/v1/dashboard/*` | Analytics | REST |
| `/api/v1/accounts/*` | Account | REST |
| `/api/v1/account-groups/*` | Account | REST |
| `/api/v1/goals/*` | Goal | REST |
| `/api/v1/users/*` | User | REST |
| `/api/v1/graphql` | Analytics (read gateway — exposes `transactions` and `categories` queries against the MySQL projection) | GraphQL |

Transactions, planned-transactions and categories are owned by `transaction-service` on port 8002. REST writes go there; the monolith only reads the projected copy.

### Banking endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/bank/available-banks?country=DK` | List available banks |
| `POST` | `/api/v1/bank/connect` | Start OAuth authorization flow |
| `GET` | `/api/v1/bank/callback` | OAuth callback (bank redirects here) |
| `GET` | `/api/v1/bank/connections?account_id=1` | List connected bank accounts |
| `POST` | `/api/v1/bank/connections/{id}/sync` | Sync transactions from bank |
| `DELETE` | `/api/v1/bank/connections/{id}` | Disconnect a bank |

### Categorization pipeline

The `CategorizationService` in `category/application/categorization_service.py` orchestrates a multi-tier pipeline:

1. **Rule Engine** — Keyword-based matching with longest-match-first, sign-dependent overrides
2. **ML Categorizer** — Port defined (`IMlCategorizer`), adapter not yet implemented
3. **LLM Categorizer** — Port defined (`ILlmCategorizer`), adapter not yet implemented
4. **Fallback** — Default "Ovrigt" subcategory when no tier matches

Each transaction stores its `categorization_tier` ("rule", "ml", "llm", "fallback") and `categorization_confidence` for pipeline visibility.

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
| `ENABLE_BANKING_APP_ID` | Enable Banking application ID | — |
| `ENABLE_BANKING_KEY_PATH` | Path to PEM private key file | `./enablebanking-sandbox.pem` |
| `ENABLE_BANKING_REDIRECT_URI` | OAuth redirect URI | `http://localhost:8000/api/v1/bank/callback` |
| `ENABLE_BANKING_ENVIRONMENT` | `sandbox` or `production` | `sandbox` |
| `TRANSACTION_SERVICE_URL` | Base URL for transaction-service (used by banking bulk-import) | `http://transaction-service:8002` |
| `TRANSACTION_SERVICE_TIMEOUT` | HTTP timeout in seconds | `10` |

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
