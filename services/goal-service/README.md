# Goal Service

Standalone microservice for managing savings goals. Uses PostgreSQL with `NUMERIC(12,2)` for exact decimal arithmetic, validates JWTs issued by user-service, and publishes goal events via the transactional outbox pattern.

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL (port 5438 via docker-compose)
- RabbitMQ (port 5672 via docker-compose)

### Install and run

```bash
cd services/goal-service
uv sync --dev
uv run uvicorn app.main:app --host 0.0.0.0 --port 8006 --reload
```

Or via docker-compose from the project root:

```bash
docker compose up -d postgres-goals rabbitmq user-service goal-service goal-outbox-worker
```

### Health Check

```bash
curl http://localhost:8006/health
# {"status": "healthy", "service": "goal-service"}
```

## Architecture

```text
app/
├── main.py              # FastAPI app, routes, health check
├── config.py            # Pydantic BaseSettings (env vars)
├── auth.py              # JWT validation only (no token creation)
├── database.py          # Async SQLAlchemy engine + session factory
├── models.py            # GoalModel, OutboxEventModel, GoalAllocationHistoryModel
├── dependencies.py      # FastAPI DI wiring
├── domain/
│   ├── entities.py      # Goal (frozen dataclass)
│   └── exceptions.py    # GoalNotFoundException
├── application/
│   ├── ports/
│   │   ├── inbound.py   # IGoalService interface
│   │   └── outbound.py  # Repository, UoW, EventPublisher interfaces
│   ├── dto.py           # GoalCreate, GoalBase DTOs
│   ├── service.py       # GoalService (CRUD + outbox events)
│   └── budget_month_closed_handler.py  # ADR-0003 allocation logic
├── adapters/
│   └── outbound/
│       ├── postgres_goal_repository.py
│       ├── postgres_goal_allocation_repository.py
│       ├── postgres_outbox_repository.py
│       ├── account_adapter.py          # Resolves account ownership via account-service
│       ├── unit_of_work.py
│       └── rabbitmq_publisher.py
├── workers/
│   └── outbox_publisher.py  # Polls outbox, publishes to RabbitMQ
└── migrations/              # Alembic migrations
```

### Key Architecture Decisions

- **Unit of Work pattern**: All repositories share the same `AsyncSession`. Domain writes and outbox events are committed atomically.
- **Transactional outbox**: Events written to `outbox_events` in the same DB transaction as domain data. Standalone worker publishes to RabbitMQ with `SELECT ... FOR UPDATE SKIP LOCKED`.
- **Account validation**: Goal creation resolves ownership through account-service via one HTTP call (with configurable timeout); account-service distinguishes a missing account from upstream failure.
- **No foreign keys**: `user_id` and `account_id` are plain integers with no FK constraints to other services.
- **ADR-0003 support**: Schema includes `goal_allocation_history`, `unallocated_budget_surplus`, and `is_default_savings_goal` for automatic budget surplus allocation (consumer not yet implemented).

## API Endpoints

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `POST` | `/api/v1/goals` | Create goal | Yes |
| `GET` | `/api/v1/goals/{id}` | Get goal by ID | Yes |
| `PUT` | `/api/v1/goals/{id}` | Update goal | Yes |
| `DELETE` | `/api/v1/goals/{id}` | Delete goal | Yes |
| `GET` | `/health` | Health check | No |

## Event Publishing (Transactional Outbox)

On goal mutations, events are written to the `outbox_events` table in the same DB transaction. A standalone outbox worker publishes them to RabbitMQ.

| Event | Routing Key | Trigger |
|-------|-------------|---------|
| `GoalCreatedEvent` | `goal.created` | Create goal |
| `GoalUpdatedEvent` | `goal.updated` | Update goal |
| `GoalDeletedEvent` | `goal.deleted` | Delete goal |

## Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | — | PostgreSQL async connection string |
| `RABBITMQ_URL` | No | `amqp://guest:guest@rabbitmq:5672/` | RabbitMQ connection |
| `JWT_SECRET` | Yes | — | JWT signing key (must match user-service) |
| `JWT_ALGORITHM` | No | `HS256` | JWT algorithm |
| `USER_SERVICE_URL` | No | `http://user-service:8001` | User-service URL for account validation |
| `USER_SERVICE_TIMEOUT` | No | `2.0` | HTTP timeout for user-service calls (seconds) |
| `INTERNAL_API_KEY` | Yes | — | Internal API key for service-to-service auth; startup fails without it (P1-15) |
| `ENVIRONMENT` | No | `development` | Runtime environment |

## Testing

```bash
# All tests via Makefile
make test

# Unit tests (service logic, API routes, repository, budget handler)
uv run pytest tests/unit/ -v

# Integration tests (API round-trip, outbox worker, UoW)
uv run pytest tests/integration/ -v

# Migration tests (ADR-0003 schema)
uv run pytest tests/migrations/ -v

# Quality checks
make check
```

### Test Files

- `tests/unit/test_goal_service.py` — service-layer behavior and outbox writing
- `tests/unit/test_goal_repository.py` — repository CRUD against an in-memory database
- `tests/unit/test_goal_api.py` — FastAPI route behavior with dependency overrides
- `tests/unit/test_budget_month_closed_handler.py` — ADR-0003 allocation handler logic
- `tests/integration/test_goal_api_integration.py` — API to service to repository round trip
- `tests/integration/test_budget_month_closed_uow_integration.py` — allocation handler with UoW
- `tests/integration/test_outbox_worker_integration.py` — worker publishes pending events (in `tests/unit/`)
- `tests/integration/test_outbox_worker_retry_integration.py` — worker marks failures and retries
- `tests/integration/test_outbox_worker_multiattempt_integration.py` — repeated retry flow
- `tests/migrations/test_adr_0003_goal_allocation_migration.py` — schema migration verification

## Database

- **Engine**: PostgreSQL 16 (async via `asyncpg`)
- **ORM**: SQLAlchemy 2.0 async with `Mapped[]` type annotations
- **Migrations**: Alembic
- **Port**: 5438 (host) → 5432 (container) in docker-compose

## ADR-0003: Budget Surplus Allocation

The goal-service schema supports automatic allocation of budget surplus to a default savings goal. See [ADR-0003](../../docs/adr/0003-goal-allocation-from-budget-surplus.md) for full details.

What is implemented:
- Schema: `goal_allocation_history`, `unallocated_budget_surplus` tables
- `is_default_savings_goal` flag on goals with partial unique index
- `BudgetMonthClosedHandler` application-layer handler
- SQLAlchemy repositories and UoW for the handler

What is still needed for the runtime flow:
1. RabbitMQ consumer in goal-service that deserializes `budget.month_closed` events
2. Monolith publisher and day-7 scheduled close job
3. Frontend support for selecting a default savings goal
