# Transaction Service

Standalone microservice for financial transaction management, category ownership, CSV import, and planned transactions. Uses PostgreSQL with `NUMERIC(12,2)` for exact decimal arithmetic.

This service **validates** JWT tokens but does **not issue** them — users authenticate via user-service and use that token here. Categories are owned by this service and synced to categorization-service via RabbitMQ events.

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
├── main.py              # FastAPI app, lifespan, exception handlers
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
│   ├── outbox_publisher.py  # Polls outbox, publishes to RabbitMQ
│   └── transaction_categorized_consumer.py  # Consumes transaction.categorized events
├── alembic.ini
└── migrations/
```

### Key Architecture Decisions

- **Unit of Work pattern**: All repositories share the same `AsyncSession` via `SQLAlchemyUnitOfWork`. Domain writes and outbox events are committed atomically, eliminating the dual-write problem.
- **Transactional outbox**: Events are written to `outbox_events` in the same DB transaction as domain data. A standalone worker polls the table with `SELECT ... FOR UPDATE SKIP LOCKED` and publishes to RabbitMQ. Guarantees at-least-once delivery.
- **Category ownership**: This service is the source of truth for categories. Changes are published as `category.created/updated/deleted` events, consumed by categorization-service's category sync consumer.
- **Denormalized names**: `account_name` and `category_name` are stored alongside IDs. No cross-service database calls.
- **No foreign keys**: `user_id`, `account_id` are plain integers — no FK constraints to other services' databases.
- **Data isolation**: Every transaction query filters by `user_id` for multi-tenant security.
- **Categorization integration**: On create, the service calls `categorization-service` (HTTP, 500ms timeout) for sync tier-1 categorization. On timeout or failure, falls back gracefully to uncategorized. The async pipeline overwrites via the `transaction.categorized` consumer.
- **Bulk import with dedup**: `POST /bulk` accepts batches (used by bank sync). Deduplicates on `(user_id, date, amount, description)` and skips existing entries.
- **Amount constraint**: `CHECK (amount > 0)` enforced at database level. Direction carried by `transaction_type` enum.

## API Endpoints

### Transactions

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `POST` | `/api/v1/transactions/` | Create transaction | Yes |
| `GET` | `/api/v1/transactions/` | List (with filters) — returns a `{total_count, items}` envelope, **not** a bare array | Yes |
| `GET` | `/api/v1/transactions/{id}` | Get by ID | Yes |
| `DELETE` | `/api/v1/transactions/{id}` | Delete transaction | Yes |
| `POST` | `/api/v1/transactions/import-csv` | Import CSV file | Yes |
| `POST` | `/api/v1/transactions/bulk` | Bulk import with deduplication (used by bank sync) | Service JWT |

### Planned Transactions

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `POST` | `/api/v1/planned-transactions/` | Create planned | Yes |
| `GET` | `/api/v1/planned-transactions/` | List (active_only filter) | Yes |
| `PATCH` | `/api/v1/planned-transactions/{id}` | Update planned | Yes |
| `DELETE` | `/api/v1/planned-transactions/{id}` | Deactivate (soft delete) | Yes |

### Categories — **not served by this service**

Per ADR-003, categorization-service (`:8005`) is the sole owner and writer of the
taxonomy; this service keeps event-synced read copies only and has no category
routes. The table that used to sit here documented `POST`/`PUT`/`DELETE
/api/v1/categories/` on `:8002` and had been stale since the ADR-003 cutover.

Since P2-28 those writes are on no public prefix anywhere: they live at
`/api/v1/internal/categories/…` on `:8005` behind `X-Internal-API-Key`, and the
perimeter answers 404 for the `/api/v1/internal/` prefix. Reads
(`GET /api/v1/categories/`, `GET /api/v1/subcategories/`) are unchanged on `:8005`.

### Query Filters

`GET /api/v1/transactions/` supports:
- `account_id` — filter by account
- `category_id` — filter by category
- `start_date` / `end_date` — date range filter
- `transaction_type` — `income` or `expense`
- `skip` / `limit` — pagination (default: 0/50, max limit: 200). Out of range is a **422**,
  not a 500: the bounds sit on `Query(...)` at the HTTP boundary, where FastAPI can still
  translate them, and are duplicated on `TransactionFiltersDTO` for non-HTTP callers.

### List response shape

`GET /api/v1/transactions/` returns an envelope (P1-14, breaking):

```json
{ "total_count": 93, "items": [ { "id": 1, "...": "..." } ] }
```

`total_count` is the size of the **filtered set**, not of the returned page — a page of 50
out of 93 says so, so a caller can tell "here is a page" from "that is all there was". Rows
and count are read in the same DB transaction; under READ COMMITTED a concurrent insert can
leave the total one ahead of the page, which is accepted (no row is lost or duplicated).

Callers must send `skip`/`limit` explicitly — the default page of 50 is what silently
truncated both the transactions page and analytics' backfill before P1-14. `PAGE_SIZE` in
`analytics-service/app/tools/backfill.py` is 200 and sits exactly on the `le` bound: raise it
and every page 422s.

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
| `CategoryCreatedEvent` | `category.created` | categorization-category-sync |
| `CategoryUpdatedEvent` | `category.updated` | categorization-category-sync |
| `CategoryDeletedEvent` | `category.deleted` | categorization-category-sync |

### Inbound Events (consumed)

| Event | Routing Key | Action |
|-------|-------------|--------|
| `TransactionCategorizedEvent` | `transaction.categorized` | Overwrites `category_id`, `category_name`, `categorization_tier` on the transaction |

The consumer uses an inbox pattern (`processed_events` table) for idempotency.

The `amount` field in transaction events is serialized as a string to preserve decimal precision across JSON serialization.

## Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | — | PostgreSQL async connection string |
| `RABBITMQ_URL` | No | `amqp://guest:guest@localhost:5672/` | RabbitMQ connection |
| `JWT_SECRET` | Yes | — | JWT signing key (must match user-service) |
| `JWT_ALGORITHM` | No | `HS256` | JWT algorithm |
| `ENVIRONMENT` | No | `development` | Runtime environment |
| `CATEGORIZATION_SERVICE_URL` | No | `http://categorization-service:8005` | Categorization service base URL |

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
