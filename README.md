# Finance Tracker — Microservices Personal Finance Application

A personal finance tracking application being incrementally migrated from a **monolith** to **microservices**. The backend uses FastAPI with hexagonal architecture (ports & adapters), CQRS, event-driven communication via RabbitMQ, and polyglot persistence (MySQL + PostgreSQL).

## Table of Contents

- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Service Map](#service-map)
- [Project Structure](#project-structure)
- [API Reference](#api-reference)
- [Event-Driven Architecture](#event-driven-architecture)
- [Configuration](#configuration)
- [Testing](#testing)
- [Security](#security)
- [Development](#development)
- [Documentation](#documentation)

---

## Quick Start

### Prerequisites

- Python 3.11+
- `uv` (Python package manager)
- Node.js 18+ (for frontend)
- Docker Desktop

### Start everything

```bash
docker compose up -d
```

This starts all services:

| Service | Port | Description |
|---------|------|-------------|
| MySQL | 3306 | Monolith database |
| PostgreSQL (users) | 5433 | User-service database |
| PostgreSQL (transactions) | 5434 | Transaction-service database |
| RabbitMQ | 5672 / 15672 | Event bus + management UI |
| Monolith | 8000 | Accounts, budgets, categories, goals, analytics |
| User Service | 8001 | Registration, login, JWT issuing |
| Transaction Service | 8002 | Transaction CRUD, CSV import, planned transactions |
| User Outbox Worker | — | Polls outbox table, publishes user events to RabbitMQ |
| Transaction Outbox Worker | — | Polls outbox table, publishes transaction events to RabbitMQ |
| UserSync Consumer | — | Syncs users from events to MySQL |
| AccountCreation Consumer | — | Creates default accounts from events |

**Wait 30-60 seconds** for health checks to pass.

### Frontend

```bash
cd frontend/finans-tracker-frontend
yarn install
yarn dev
```

App: http://localhost:3001

### Verify services

```bash
curl http://localhost:8000/health   # Monolith
curl http://localhost:8001/health   # User Service
curl http://localhost:8002/health   # Transaction Service
```

See [INSTALLATION.md](INSTALLATION.md) for detailed setup including database seeding.

---

## Architecture

### System Overview

The application is being incrementally extracted from a monolith to microservices. Currently extracted: **user-service** and **transaction-service**. The monolith handles everything else and receives event-driven updates.

```mermaid
graph LR
    FE[React Frontend] -->|register/login| US[User Service<br/>:8001]
    FE -->|transactions| TS[Transaction Service<br/>:8002]
    FE -->|accounts, budgets,<br/>categories, goals| MON[Monolith<br/>:8000]

    US -->|"write domain data +<br/>outbox event (same tx)"| PG_U[(PostgreSQL<br/>Users + outbox)]
    TS -->|"write domain data +<br/>outbox event (same tx)"| PG_T[(PostgreSQL<br/>Transactions + outbox)]

    PG_U -->|poll pending| UOW[User Outbox<br/>Worker]
    PG_T -->|poll pending| TOW[Transaction Outbox<br/>Worker]

    UOW -->|publish| RMQ[RabbitMQ]
    TOW -->|publish| RMQ

    RMQ -->|user.created| USC[UserSync<br/>Consumer]
    RMQ -->|user.created| ACC[AccountCreation<br/>Consumer]

    USC -->|INSERT User| MYSQL[(MySQL)]
    ACC -->|INSERT Account| MYSQL

    MON --> MYSQL
```

### Key Architecture Decisions

| Decision | Rationale |
|----------|-----------|
| **Polyglot persistence** | PostgreSQL for microservices (NUMERIC for money, async), MySQL for monolith |
| **No cross-service FKs** | Services own their data. `user_id` in monolith tables is a plain integer, no FK constraint |
| **Event-driven sync** | `user.created` events trigger MySQL user sync and default account creation |
| **Shared JWT secret** | All services validate tokens with the same secret. User-service is the sole token issuer |
| **Transactional outbox** | Domain data and event are written in the same DB transaction, eliminating the dual-write problem. A background worker polls the outbox table with `SELECT … FOR UPDATE SKIP LOCKED` and publishes to RabbitMQ. Guarantees at-least-once delivery |
| **Denormalized data** | Transaction-service stores `account_name` and `category_name` alongside IDs |
| **Amount as string in events** | Preserves decimal precision across JSON serialization |

### Hexagonal Architecture (per service)

Each bounded context follows the same structure:

```text
adapters/
├── inbound/       # REST API controllers
└── outbound/      # Repository implementations, event publishers
application/
├── ports/         # Inbound + outbound interfaces (ABC)
├── service.py     # Application service (business rules)
└── dto.py         # Pydantic DTOs with BVA validation
domain/
├── entities.py    # Frozen dataclasses (immutable domain objects)
└── exceptions.py  # Domain exceptions
```

### CQRS Split

| Operation | Protocol | Example |
|-----------|----------|---------|
| Commands (write) | REST | `POST /api/v1/transactions/` |
| Queries (read) | GraphQL | `query { financialOverview { ... } }` |
| Domain-specific reads | REST | `GET /api/v1/transactions/` |

### Dependency Injection Flow

```mermaid
sequenceDiagram
    participant Route as Inbound Adapter
    participant DI as dependencies.py
    participant Service as Application Service
    participant Port as Outbound Port
    participant Repo as Repository Adapter

    Route->>DI: Depends(get_service)
    DI->>Repo: Instantiate repository adapter
    DI->>Service: Inject repository via constructor
    Route->>Service: service.create(data)
    Service->>Port: self._repo.create(...)
    Port->>Repo: PostgreSQL/MySQL implementation
    Repo-->>Service: Domain entity
    Service-->>Route: Result
```

---

## Service Map

### Currently Deployed

| Service | Port | Database | Role |
|---------|------|----------|------|
| **Monolith** | 8000 | MySQL (3306) | Accounts, categories, budgets, goals, analytics, GraphQL gateway |
| **User Service** | 8001 | PostgreSQL (5433) | User registration, login, JWT issuing (source of truth) |
| **Transaction Service** | 8002 | PostgreSQL (5434) | Transaction CRUD, CSV import, planned transactions |
| **User Outbox Worker** | — | PostgreSQL (5433) | Polls `outbox_events`, publishes user events to RabbitMQ |
| **Transaction Outbox Worker** | — | PostgreSQL (5434) | Polls `outbox_events`, publishes transaction events to RabbitMQ |
| **UserSync Consumer** | — | MySQL | Sync user data from events to MySQL User table |
| **AccountCreation Consumer** | — | MySQL | Create default account from user.created events |

### Future Services (not yet extracted)

| Service | Planned Port | Description |
|---------|-------------|-------------|
| Budget Service | 8003 | Budget management |
| Analytics Service | 8004 | GraphQL gateway + Elasticsearch |
| AI Service | 8005 | Transaction categorization (rule/ML/LLM) |
| Notification Service | 8006 | Email/push notifications |
| API Gateway | — | Routing, rate limiting, JWT validation |

---

## Project Structure

```
finance-tracker/
├── backend/                         # Monolith (FastAPI)
│   ├── main.py                      # App, middleware, router registration
│   ├── config.py                    # Environment configuration
│   ├── auth.py                      # JWT auth (creates + validates tokens)
│   ├── dependencies.py              # FastAPI DI wiring
│   ├── consumers/                   # RabbitMQ event consumers
│   │   ├── base.py                  # BaseConsumer (retry, DLQ, idempotency)
│   │   ├── user_sync.py             # UserSyncConsumer
│   │   ├── account_creation.py      # AccountCreationConsumer
│   │   └── worker.py                # Consumer runner (--consumer flag)
│   ├── transaction/                 # Bounded context (hexagonal)
│   ├── category/                    # Bounded context
│   ├── budget/                      # Legacy budget context
│   ├── monthly_budget/              # Aggregate-based monthly budgets
│   ├── analytics/                   # Dashboard + GraphQL read gateway
│   ├── account/                     # Account + groups
│   ├── goal/                        # Goals
│   ├── user/                        # Local user management
│   ├── shared/                      # Cross-cutting ports/adapters
│   ├── models/mysql/                # SQLAlchemy ORM models
│   ├── database/                    # Connection managers
│   └── tests/                       # Unit + integration tests
│
├── services/
│   ├── user-service/                # User microservice
│   │   ├── app/                     # FastAPI app (hexagonal)
│   │   │   └── workers/             # Outbox publisher worker
│   │   ├── migrations/              # Alembic migrations (incl. outbox_events)
│   │   ├── tests/                   # Unit + integration tests
│   │   └── Dockerfile
│   │
│   ├── transaction-service/         # Transaction microservice
│   │   ├── app/                     # FastAPI app (hexagonal + UoW)
│   │   │   └── workers/             # Outbox publisher worker
│   │   ├── migrations/              # Alembic migrations (incl. outbox_events)
│   │   ├── tests/                   # Unit + integration tests
│   │   └── Dockerfile
│   │
│   └── shared/
│       └── contracts/               # Shared event schemas (Pydantic)
│           └── contracts/events/    # UserCreated, TransactionCreated, etc.
│
├── frontend/
│   └── finans-tracker-frontend/     # React SPA (Vite)
│       ├── src/
│       │   ├── components/          # UI components
│       │   ├── pages/               # Page components
│       │   ├── context/             # Auth context
│       │   ├── hooks/               # Custom hooks
│       │   └── utils/               # API client
│       └── package.json
│
├── tests/
│   └── e2e/                         # End-to-end tests (cross-service)
│
├── docker-compose.yml               # Full stack orchestration
├── INSTALLATION.md
└── README.md
```

---

## API Reference

### User Service (port 8001)

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `POST` | `/api/v1/users/register` | Register user | No |
| `POST` | `/api/v1/users/login` | Login (returns JWT) | No |
| `GET` | `/api/v1/users/me` | Current user profile | Yes |

### Transaction Service (port 8002)

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `POST` | `/api/v1/transactions/` | Create transaction | Yes |
| `GET` | `/api/v1/transactions/` | List (with filters) | Yes |
| `GET` | `/api/v1/transactions/{id}` | Get by ID | Yes |
| `DELETE` | `/api/v1/transactions/{id}` | Delete | Yes |
| `POST` | `/api/v1/transactions/import-csv` | Import CSV | Yes |
| `POST` | `/api/v1/planned-transactions/` | Create planned | Yes |
| `GET` | `/api/v1/planned-transactions/` | List planned | Yes |
| `PATCH` | `/api/v1/planned-transactions/{id}` | Update planned | Yes |
| `DELETE` | `/api/v1/planned-transactions/{id}` | Deactivate | Yes |

### Monolith (port 8000)

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `*` | `/api/v1/transactions/*` | Transaction CRUD + CSV | Yes |
| `*` | `/api/v1/categories/*` | Category CRUD | Partial |
| `*` | `/api/v1/budgets/*` | Legacy budget CRUD | Yes |
| `*` | `/api/v1/monthly-budgets/*` | Monthly budget CRUD + copy | Yes |
| `*` | `/api/v1/dashboard/*` | Analytics | Yes |
| `*` | `/api/v1/accounts/*` | Account CRUD | Yes |
| `*` | `/api/v1/goals/*` | Goal CRUD | Yes |
| `*` | `/api/v1/users/*` | User management | Partial |
| `POST` | `/api/v1/graphql` | GraphQL read gateway | Yes |

### Authentication

All protected endpoints require `Authorization: Bearer <jwt-token>`. Tokens are issued by user-service and accepted by all services (shared JWT secret).

---

## Event-Driven Architecture

### Event Flow

```mermaid
sequenceDiagram
    participant FE as Frontend
    participant US as User Service
    participant PG as PostgreSQL
    participant OW as Outbox Worker
    participant RMQ as RabbitMQ
    participant USC as UserSync Consumer
    participant ACC as AccountCreation Consumer
    participant MYSQL as MySQL

    FE->>US: POST /register
    US->>PG: BEGIN tx
    US->>PG: INSERT user
    US->>PG: INSERT outbox_events (user.created)
    US->>PG: COMMIT
    US-->>FE: 201 + JWT token

    loop Poll every 1s
        OW->>PG: SELECT … FOR UPDATE SKIP LOCKED
        PG-->>OW: pending events
        OW->>RMQ: publish user.created
        OW->>PG: UPDATE status = 'published'
    end

    par Independent consumers
        RMQ->>USC: user.created (queue: monolith.user_sync)
        USC->>MYSQL: INSERT INTO User
    and
        RMQ->>ACC: user.created (queue: monolith.account_creation)
        ACC->>MYSQL: INSERT INTO Account
    end
```

### Event Catalog

| Event | Producer | Published via | Consumers | Routing Key |
|-------|----------|---------------|-----------|-------------|
| `UserCreatedEvent` | user-service | Outbox worker | UserSyncConsumer, AccountCreationConsumer | `user.created` |
| `TransactionCreatedEvent` | transaction-service | Outbox worker | (future consumers) | `transaction.created` |
| `TransactionDeletedEvent` | transaction-service | Outbox worker | (future consumers) | `transaction.deleted` |
| `AccountCreatedEvent` | AccountCreationConsumer | Direct publish | (future consumers) | `account.created` |

### Transactional Outbox (Event Publishing)

Both user-service and transaction-service use the **transactional outbox pattern** to avoid the dual-write problem:

1. Domain data and an `outbox_events` row are written in the **same database transaction**
2. A standalone **outbox worker** polls the table using `SELECT … FOR UPDATE SKIP LOCKED`
3. The worker publishes events to RabbitMQ and marks rows as `published`
4. On publish failure, exponential backoff retries (up to 5 attempts)

This guarantees **at-least-once delivery** — no event is lost even if the application crashes after commit. Downstream consumers must be idempotent.

### Consumer Reliability

All consumers inherit from `BaseConsumer` with:
- **Retry**: 3 attempts with exponential backoff
- **Dead-letter queue**: Failed messages routed to `*.dlq`
- **Idempotency**: Correlation-ID based deduplication (in-memory, planned: Redis/DB-backed)
- **Independent operation**: Each consumer has its own queue and fails independently

---

## Configuration

### Docker-Compose Environment

| Variable | Service | Default | Description |
|----------|---------|---------|-------------|
| `DATABASE_URL` | all | — | Database connection string |
| `SECRET_KEY` / `JWT_SECRET` | all | — | JWT signing key (must match) |
| `RABBITMQ_URL` | all | `amqp://guest:guest@rabbitmq:5672/` | RabbitMQ connection |
| `CORS_ORIGINS` | all | `http://localhost:3000,http://localhost:3001` | Allowed origins |
| `ENVIRONMENT` | all | `development` | Runtime environment |

The monolith uses `SECRET_KEY`, microservices use `JWT_SECRET`. Both are set to the same value in docker-compose.

See `example.env` for the full list with descriptions.

---

## Testing

The project has **370+ tests** organized following the testing pyramid:

```
     +----------+
     |   E2E    |   Cross-service flow tests (pytest + httpx)
     +----------+
     | Integr.  |   Full HTTP flow with in-memory DB
     +----------+
     |   Unit   |   Business logic + schema BVA validation
     +----------+
     |   Arch   |   Import boundary enforcement
     +----------+
```

### Test Counts by Service

| Service | Unit | Integration | E2E | Total |
|---------|------|-------------|-----|-------|
| Monolith | ~231 | 45 | — | ~276 |
| User Service | 27 | 11 | — | 38 |
| Transaction Service | 41 | 17 | — | 58 |
| Cross-service E2E | — | — | ~15 | ~15 |

### Running Tests

```bash
# Monolith tests
cd backend && uv run pytest tests/ -v

# User service tests
cd services/user-service && uv run pytest tests/ -v

# Transaction service tests
cd services/transaction-service && uv run pytest tests/ -v

# E2E tests (requires docker compose up)
uv run pytest tests/e2e/ -v -m e2e
```

---

## Security

- **JWT Authentication** — user-service issues tokens, all services validate with shared secret
- **Cross-service token compatibility** — tokens contain both `sub` (standard) and legacy `user_id`/`username`/`email` fields
- **Data isolation** — every query filters by `user_id` (multi-tenant). Wrong user gets 404, not 403 (no existence leaking)
- **bcrypt password hashing** — 12 rounds in user-service
- **Input validation** — Pydantic schemas with BVA (Boundary Value Analysis) at all service boundaries
- **No cross-service FKs** — services cannot accidentally access each other's data
- **Correlation ID** — every request gets a traceable UUID for audit and debugging
- **CORS** — configurable allowed origins per service

---

## Development

### Full Stack (Docker)

```bash
docker compose up -d
# All services: http://localhost:8000 (monolith), :8001 (user), :8002 (transaction)
# RabbitMQ UI: http://localhost:15672 (guest/guest)
# Frontend: http://localhost:3001
```

### Local Development (without Docker)

```bash
# Backend (monolith)
cd backend && uv sync
uv run uvicorn backend.main:app --reload --port 8000

# User service
cd services/user-service
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001

# Transaction service
cd services/transaction-service
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8002

# Consumers (in separate terminals)
uv run python -m backend.consumers.worker --consumer user-sync
uv run python -m backend.consumers.worker --consumer account-creation

# Frontend
cd frontend/finans-tracker-frontend
yarn install && yarn dev
```

### Default Credentials (development)

| Service | Username | Password |
|---------|----------|----------|
| MySQL | `root` | `root` |
| RabbitMQ | `guest` | `guest` |

---

## Documentation

| Document | Description |
|----------|-------------|
| [INSTALLATION.md](INSTALLATION.md) | Full setup guide with Docker and seeding |
| [backend/README.md](backend/README.md) | Monolith architecture, router map, consumers |
| [backend/docs/STRUCTURE.md](backend/docs/STRUCTURE.md) | Hexagonal structure map and bounded contexts |
| [services/user-service/README.md](services/user-service/README.md) | User service API, events, JWT format |
| [services/transaction-service/README.md](services/transaction-service/README.md) | Transaction service API, UoW pattern, CSV import |
| [services/shared/contracts/README.md](services/shared/contracts/README.md) | Shared event contracts (Pydantic models) |
| [docs/microservice-architecture.mermaid](docs/microservice-architecture.mermaid) | Full architecture diagram (current + future) |
| [backend/DATABASE_COMPARISON.md](backend/DATABASE_COMPARISON.md) | MySQL vs Elasticsearch vs Neo4j comparison |
| [docs/MANDATORY_ASSIGNMENT_1_REPORT.md](docs/MANDATORY_ASSIGNMENT_1_REPORT.md) | Assignment 1 report |

---

## Roadmap

- [x] Hexagonal architecture (ports & adapters) across all domains
- [x] GraphQL read gateway (CQRS pattern)
- [x] Multi-database support (MySQL, Elasticsearch, Neo4j)
- [x] JWT authentication with bcrypt
- [x] API versioning (`/api/v1/`)
- [x] Structured logging with correlation ID
- [x] Monthly budget system with aggregate model
- [x] Unit of Work pattern for transactional boundaries
- [x] Architecture fitness tests (import boundary enforcement)
- [x] 370+ tests (unit, integration, e2e)
- [x] User-service extraction (PostgreSQL, RabbitMQ events)
- [x] Transaction-service extraction (PostgreSQL, UoW, CSV import)
- [x] Event-driven sync (UserSync + AccountCreation consumers)
- [x] Cross-service JWT compatibility
- [x] No cross-service foreign key constraints
- [ ] API Gateway (routing, rate limiting)
- [ ] Budget service extraction
- [ ] Analytics service + Elasticsearch
- [ ] AI categorization service
- [ ] Frontend routing to microservices (currently partial)
- [x] Transactional outbox pattern (at-least-once delivery, dual-write elimination)
- [ ] Consumer idempotency store (Redis/DB-backed, replacing in-memory dedup)
