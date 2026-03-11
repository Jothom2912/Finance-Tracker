# Transaction Service

Standalone microservice for financial transaction management, CSV import, and planned transactions. Uses PostgreSQL with `NUMERIC(12,2)` for exact decimal arithmetic.

This service **validates** JWT tokens but does **not issue** them — users authenticate via user-service and use that token here.

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL (port 5434 via docker-compose)
- RabbitMQ (port 5672 via docker-compose)

### Install and run

```bash
cd services/transaction-service
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8002
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
├── models.py            # TransactionModel, PlannedTransactionModel
├── dependencies.py      # FastAPI DI wiring (shared session for UoW)
├── domain/
│   ├── entities.py      # Transaction, PlannedTransaction (frozen dataclasses)
│   └── exceptions.py    # TransactionNotFoundException, etc.
├── application/
│   ├── ports/
│   │   ├── inbound.py   # ITransactionService interface
│   │   └── outbound.py  # Repository, UoW, EventPublisher interfaces
│   ├── dto.py           # DTOs with BVA validation
│   └── service.py       # TransactionService (UoW pattern, event publish after commit)
├── adapters/
│   ├── inbound/
│   │   └── rest_api.py  # FastAPI router (transactions + planned transactions)
│   └── outbound/
│       ├── postgres_transaction_repository.py
│       ├── postgres_planned_repository.py
│       ├── unit_of_work.py
│       └── rabbitmq_publisher.py
├── alembic.ini
└── migrations/
```

### Key Architecture Decisions

- **Unit of Work pattern**: Repositories use `flush()`, service controls `commit()`/`rollback()` via `IUnitOfWork`. All repositories and UoW share the same `AsyncSession`.
- **Event publish after commit**: Events are published to RabbitMQ after the database transaction commits. If publish fails, the transaction is still persisted (at-least-once pattern). Transactional outbox is a future improvement.
- **Denormalized names**: `account_name` and `category_name` are stored alongside IDs. No cross-service database calls.
- **No foreign keys**: `user_id`, `account_id`, `category_id` are plain integers — no FK constraints to other services' databases.
- **Data isolation**: Every query filters by `user_id` for multi-tenant security.

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

### Query Filters

`GET /api/v1/transactions/` supports:
- `account_id` — filter by account
- `category_id` — filter by category
- `start_date` / `end_date` — date range filter
- `transaction_type` — `income` or `expense`
- `skip` / `limit` — pagination (default: 0/50, max limit: 200)

## Event Publishing

On transaction create/delete, the service publishes events to RabbitMQ:

```json
{
  "event_type": "transaction.created",
  "transaction_id": 1,
  "user_id": 6,
  "amount": "125.50",
  "transaction_type": "expense",
  "account_id": 1
}
```

The `amount` field is serialized as a string to preserve decimal precision across JSON serialization.

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
# Unit tests (40 tests — service logic + DTO BVA validation)
uv run pytest tests/unit/ -v

# Integration tests (17 tests — full HTTP flow with SQLite)
uv run pytest tests/integration/ -v

# All tests (57 total)
uv run pytest tests/ -v
```

## Database

- **Engine**: PostgreSQL 16 (async via `asyncpg`)
- **Amount type**: `NUMERIC(12,2)` — exact decimal arithmetic, no floating-point
- **ORM**: SQLAlchemy 2.0 async with `Mapped[]` type annotations
- **Migrations**: Alembic
- **Port**: 5434 (host) → 5432 (container) in docker-compose
- **Indexes**: `user_id`, `date`, `account_id`, `category_id` for query performance
