# Transaction Service

Standalone microservice for financial transaction management, category ownership, CSV import, and planned transactions. Uses PostgreSQL with `NUMERIC(12,2)` for exact decimal arithmetic.

This service **validates** JWT tokens but does **not issue** them — users authenticate via user-service and use that token here. Categories are owned by this service and synced to the monolith via RabbitMQ events.

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL (port 5434 via docker-compose)
- RabbitMQ (port 5672 via docker-compose)

### Install and run

```bash
cd services/transaction-service
uv sync --dev
uv run uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload
```

Or via docker-compose from the project root:

```bash
docker compose up transaction-service
```

### Health Check

```bash
curl http://localhost:8002/health
# {"status": "healthy", "service": "transaction-service"}
```

## Architecture

```text
app/
├── main.py              # FastAPI app, lifespan, CORS, exception handlers
├── config.py            # Pydantic BaseSettings (env vars)
├── auth.py              # JWT validation only (no token creation)
├── database.py          # Async SQLAlchemy engine + session factory
├── models.py            # TransactionModel, PlannedTransactionModel, CategoryModel, OutboxEventModel
├── dependencies.py      # FastAPI DI wiring (shared session for UoW)
├── domain/
│   ├── entities.py      # Transaction, PlannedTransaction, Category (frozen dataclasses)
│   └── exceptions.py    # TransactionNotFoundException, CategoryInUseException, etc.
├── application/
│   ├── ports/
│   │   ├── inbound.py   # ITransactionService, ICategoryService interfaces
│   │   └── outbound.py  # Repository, UoW, EventPublisher interfaces
│   ├── dto.py           # DTOs with BVA validation
│   ├── service.py       # TransactionService (UoW pattern, transactional outbox)
│   └── category_service.py  # CategoryService (CRUD + outbox events)
├── adapters/
│   ├── inbound/
│   │   ├── rest_api.py       # FastAPI router (transactions + planned transactions)
│   │   └── category_api.py   # FastAPI router (categories)
│   └── outbound/
│       ├── postgres_transaction_repository.py
│       ├── postgres_planned_repository.py
│       ├── postgres_category_repository.py
│       ├── postgres_outbox_repository.py
│       ├── unit_of_work.py
│       └── rabbitmq_publisher.py
├── workers/
│   └── outbox_publisher.py  # Polls outbox, publishes to RabbitMQ
├── alembic.ini
└── migrations/
```

### Key Architecture Decisions

- **Unit of Work pattern**: All repositories share the same `AsyncSession` via `SQLAlchemyUnitOfWork`. Domain writes and outbox events are committed atomically, eliminating the dual-write problem.
- **Transactional outbox**: Events are written to `outbox_events` in the same DB transaction as domain data. A standalone worker polls the table with `SELECT ... FOR UPDATE SKIP LOCKED` and publishes to RabbitMQ. Guarantees at-least-once delivery.
- **Category ownership**: This service is the source of truth for categories. Changes are published as `category.created/updated/deleted` events, consumed by `CategorySyncConsumer` in the monolith.
- **Denormalized names**: `account_name` and `category_name` are stored alongside IDs. No cross-service database calls.
- **No foreign keys**: `user_id`, `account_id` are plain integers — no FK constraints to other services' databases.
- **Data isolation**: Every transaction query filters by `user_id` for multi-tenant security.

## API Endpoints

### Transactions

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `POST` | `/api/v1/transactions/` | Create transaction | Yes |
| `GET` | `/api/v1/transactions/` | List (with filters) | Yes |
| `GET` | `/api/v1/transactions/{id}` | Get by ID | Yes |
| `DELETE` | `/api/v1/transactions/{id}` | Delete transaction | Yes |
| `POST` | `/api/v1/transactions/import-csv` | Import CSV file | Yes |

### Planned Transactions

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `POST` | `/api/v1/planned-transactions/` | Create planned | Yes |
| `GET` | `/api/v1/planned-transactions/` | List (active_only filter) | Yes |
| `PATCH` | `/api/v1/planned-transactions/{id}` | Update planned | Yes |
| `DELETE` | `/api/v1/planned-transactions/{id}` | Deactivate (soft delete) | Yes |

### Categories

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `POST` | `/api/v1/categories/` | Create category | Yes |
| `GET` | `/api/v1/categories/` | List all categories | Yes |
| `GET` | `/api/v1/categories/{id}` | Get by ID | Yes |
| `PUT` | `/api/v1/categories/{id}` | Update category | Yes |
| `DELETE` | `/api/v1/categories/{id}` | Delete (if no transactions reference it) | Yes |

### Query Filters

`GET /api/v1/transactions/` supports:
- `account_id` — filter by account
- `category_id` — filter by category
- `start_date` / `end_date` — date range filter
- `transaction_type` — `income` or `expense`
- `skip` / `limit` — pagination (default: 0/50, max limit: 200)

## Event Publishing (Transactional Outbox)

On transaction and category mutations, events are written to the `outbox_events` table in the same DB transaction. A standalone outbox worker publishes them to RabbitMQ.

### Transaction Events

| Event | Routing Key | Trigger |
|-------|-------------|---------|
| `TransactionCreatedEvent` | `transaction.created` | Create / CSV import |
| `TransactionUpdatedEvent` | `transaction.updated` | Update |
| `TransactionDeletedEvent` | `transaction.deleted` | Delete |

### Category Events

| Event | Routing Key | Consumer |
|-------|-------------|----------|
| `CategoryCreatedEvent` | `category.created` | CategorySyncConsumer (monolith) |
| `CategoryUpdatedEvent` | `category.updated` | CategorySyncConsumer (monolith) |
| `CategoryDeletedEvent` | `category.deleted` | CategorySyncConsumer (monolith) |

The `amount` field in transaction events is serialized as a string to preserve decimal precision across JSON serialization.

## Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | — | PostgreSQL async connection string |
| `RABBITMQ_URL` | No | `amqp://guest:guest@localhost:5672/` | RabbitMQ connection |
| `JWT_SECRET` | Yes | — | JWT signing key (must match user-service) |
| `JWT_ALGORITHM` | No | `HS256` | JWT algorithm |
| `CORS_ORIGINS` | No | `http://localhost:3000,http://localhost:3001` | Allowed origins |
| `ENVIRONMENT` | No | `development` | Runtime environment |

## Testing

```bash
# Unit tests (61 tests — service logic, category service, DTO BVA validation)
uv run pytest tests/unit/ -v

# Integration tests (43 tests — full HTTP flow with SQLite, category API, outbox events)
uv run pytest tests/integration/ -v

# All tests (104 total)
uv run pytest tests/ -v
```

## Database

- **Engine**: PostgreSQL 16 (async via `asyncpg`)
- **Amount type**: `NUMERIC(12,2)` — exact decimal arithmetic, no floating-point
- **ORM**: SQLAlchemy 2.0 async with `Mapped[]` type annotations
- **Migrations**: Alembic
- **Port**: 5434 (host) → 5432 (container) in docker-compose
- **Indexes**: `user_id`, `date`, `account_id`, `category_id` for query performance
