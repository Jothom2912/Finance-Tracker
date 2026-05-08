# Finance Tracker — Microservices Personal Finance Application

A personal finance tracking application being incrementally migrated from a **monolith** to **microservices**. The backend uses FastAPI with hexagonal architecture (ports & adapters), CQRS, event-driven communication via RabbitMQ, and polyglot persistence (MySQL + PostgreSQL). Includes **live bank integration** via Enable Banking (PSD2 Open Banking) with automatic transaction categorization through a multi-tier pipeline (rule engine, with ML/LLM tiers prepared).

## Table of Contents

- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Bank Integration](#bank-integration)
- [Categorization Pipeline](#categorization-pipeline)
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
| MySQL | 3307 | Monolith database |
| PostgreSQL (users) | 5433 | User-service database |
| PostgreSQL (transactions) | 5434 | Transaction-service database |
| PostgreSQL (categorization) | 5435 | Categorization-service database |
| PostgreSQL (accounts) | 5436 | Account-service database |
| PostgreSQL (goals) | 5438 | Goal-service database |
| RabbitMQ | 5672 / 15672 | Event bus + management UI |
| Monolith | 8000 | Budgets, analytics, bank sync |
| User Service | 8001 | Registration, login, JWT issuing |
| Transaction Service | 8002 | Transaction CRUD, CSV import, planned transactions, categories |
| Account Service | 8004 | Account CRUD, account groups |
| Categorization Service | 8005 | Rule/ML/LLM categorization pipeline |
| Goal Service | 8006 | Savings goals and goal events |
| AI Service | 8007 | RAG-based financial Q&A (Ollama + ChromaDB) |
| User Outbox Worker | — | Polls outbox table, publishes user events to RabbitMQ |
| Transaction Outbox Worker | — | Polls outbox table, publishes transaction events to RabbitMQ |
| Account Outbox Worker | — | Polls outbox table, publishes account events to RabbitMQ |
| Goal Outbox Worker | — | Polls outbox table, publishes goal events to RabbitMQ |
| Categorization Outbox Worker | — | Polls outbox table, publishes categorization events to RabbitMQ |
| Transaction Categorized Consumer | — | Writes categorization results back to transaction-service |
| Categorization Category Sync | — | Syncs categories from transaction-service into categorization-service |
| UserSync Consumer | — | Syncs users from events to MySQL |
| AccountCreation Consumer | — | Creates default accounts in Postgres from user.created events |
| AccountSync Consumer | — | Syncs account events from Postgres to MySQL read-replica |
| CategorySync Consumer | — | Syncs categories from transaction-service to MySQL |
| TransactionSync Consumer | — | Projects transaction events into MySQL read model |

**Wait 30-60 seconds** for health checks to pass.

### Frontend

```bash
cd services/frontend
npm install
npm run dev
```

App: http://localhost:3000

### Verify services

```bash
curl http://localhost:8000/health   # Monolith
curl http://localhost:8001/health   # User Service
curl http://localhost:8002/health   # Transaction Service
curl http://localhost:8004/health   # Account Service
curl http://localhost:8005/health   # Categorization Service
curl http://localhost:8006/health   # Goal Service
curl http://localhost:8007/health   # AI Service
```

See [INSTALLATION.md](INSTALLATION.md) for detailed setup including database seeding.

---

## Architecture

### System Overview

The application is being incrementally extracted from a monolith to microservices. Currently extracted: **user-service**, **transaction-service**, **categorization-service**, **goal-service**, and **account-service**. The monolith handles budgets, analytics, and bank sync, and receives event-driven updates. The MySQL Account table is a read-replica kept in sync via account events from account-service.

```mermaid
graph LR
    FE[React Frontend] -->|register/login| US[User Service<br/>:8001]
    FE -->|transactions| TS[Transaction Service<br/>:8002]
    FE -->|accounts| AS[Account Service<br/>:8004]
    FE -->|budgets, analytics| MON[Monolith<br/>:8000]
    FE -->|goals| GS[Goal Service<br/>:8006]

    US -->|"write domain data +<br/>outbox event (same tx)"| PG_U[(PostgreSQL<br/>Users + outbox)]
    TS -->|"write domain data +<br/>outbox event (same tx)"| PG_T[(PostgreSQL<br/>Transactions + outbox)]
    AS -->|"write domain data +<br/>outbox event (same tx)"| PG_A[(PostgreSQL<br/>Accounts + outbox)]
    GS -->|"write domain data +<br/>outbox event (same tx)"| PG_G[(PostgreSQL<br/>Goals + outbox)]
    CS[Categorization Service<br/>:8005] -->|"categorize + outbox event"| PG_C[(PostgreSQL<br/>Categorization)]

    TS -->|"sync categorize<br/>(HTTP, 500ms timeout)"| CS

    PG_U -->|poll pending| UOW[User Outbox<br/>Worker]
    PG_T -->|poll pending| TOW[Transaction Outbox<br/>Worker]
    PG_A -->|poll pending| AOW[Account Outbox<br/>Worker]
    PG_G -->|poll pending| GOW[Goal Outbox<br/>Worker]
    PG_C -->|poll pending| COW[Categorization Outbox<br/>Worker]

    UOW -->|publish| RMQ[RabbitMQ]
    TOW -->|publish| RMQ
    AOW -->|publish| RMQ
    GOW -->|publish| RMQ
    COW -->|publish| RMQ

    RMQ -->|user.created| USC[UserSync<br/>Consumer]
    RMQ -->|user.created| ACC[AccountCreation<br/>Consumer]
    RMQ -->|account.*| ASC[AccountSync<br/>Consumer]
    RMQ -->|category.*| CSC[CategorySync<br/>Consumer]
    RMQ -->|transaction.*| TSC[TransactionSync<br/>Consumer]
    RMQ -->|transaction.created| CS
    RMQ -->|transaction.categorized| TCC[Transaction Categorized<br/>Consumer]
    RMQ -->|category.*| CCSC[Cat-Service<br/>Category Sync]

    USC -->|INSERT User| MYSQL[(MySQL)]
    ACC -->|INSERT Account| PG_A
    ASC -->|UPSERT Account| MYSQL
    CSC -->|SYNC Category| MYSQL
    TSC -->|UPSERT Transaction| MYSQL

    MON --> MYSQL
```

### Bank Integration (PSD2 Open Banking)

The monolith connects to real bank accounts via [Enable Banking](https://enablebanking.com/) using the PSD2 Open Banking standard. This provides live transaction data from banks like Nordea, Danske Bank, and others across Europe.

```mermaid
sequenceDiagram
    participant User as User / Browser
    participant API as Monolith API
    participant EB as Enable Banking
    participant Bank as Bank (Nordea etc.)
    participant DB as MySQL

    User->>API: POST /bank/connect
    API->>EB: Create authorization URL
    EB-->>API: Authorization URL + state
    API-->>User: Redirect to bank

    User->>Bank: Authorize via bank login
    Bank-->>API: GET /bank/callback?code=xxx

    API->>EB: Create session (exchange code)
    EB-->>API: Session ID + accounts
    API->>DB: Store BankConnection records

    User->>API: POST /bank/connections/{id}/sync
    API->>EB: Fetch transactions
    EB-->>API: Raw transactions
    API->>API: Categorize locally (rule engine)
    API->>TS: POST /api/v1/transactions/bulk (service JWT)
    TS->>TS: Dedupe + persist + outbox events
    TS-->>API: {imported, duplicates_skipped}
    TS-->>RMQ: transaction.created events
    RMQ-->>DB: TransactionSyncConsumer projects into MySQL
    API-->>User: "12 new, 3 duplicates"
```

The bank sync flow:
1. **Connect** - User authorizes via their bank's OAuth login (PSD2 consent)
2. **Session** - Enable Banking creates a session with access to account data
3. **Sync** - Monolith fetches transactions, categorises them locally, then posts the batch to `transaction-service` over HTTP. The service dedupes, persists and publishes events
4. **Projection** - `TransactionSyncConsumer` picks up the events and materialises the rows in the monolith's MySQL read model
5. **Dashboard** - New transactions appear immediately with categorization tier badges

### Categorization Pipeline

Transactions are categorized through a multi-tier orchestrator that tries increasingly expensive methods until one succeeds:

```mermaid
flowchart LR
    TX[Transaction] --> RE[Rule Engine]
    RE -->|match| Done[Store with tier=rule]
    RE -->|no match| ML[ML Categorizer]
    ML -->|match| Done2[Store with tier=ml]
    ML -->|no match| LLM[LLM Categorizer]
    LLM -->|match| Done3[Store with tier=llm]
    LLM -->|no match| FB[Fallback]
    FB --> Done4[Store with tier=fallback]
```

The hierarchy is three levels deep: **Category** (e.g., "Mad & Drikke") contains **SubCategories** (e.g., "Supermarked") which map to **Merchants** (e.g., "Netto"). The rule engine uses longest-match-first keyword matching with sign-dependent overrides (e.g., a positive "Netto" transaction is a refund, not a grocery purchase).

ML and LLM tiers are defined as ports but not yet implemented - the architecture is ready for them via the `IMlCategorizer` and `ILlmCategorizer` protocols.

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
| **REST for mutations, GraphQL for reads** | Bank sync (side effects) uses REST; dashboard data (nested reads) uses GraphQL |
| **Multi-tier categorization** | Rule engine first (fast, deterministic), then ML/LLM ports (expensive, probabilistic) |
| **PSD2 via Enable Banking** | Aggregator abstracts bank-specific APIs; JWT-signed requests; OAuth for user consent |

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
| **Monolith** | 8000 | MySQL (3307) | Budgets, analytics, GraphQL gateway, bank sync |
| **User Service** | 8001 | PostgreSQL (5433) | User registration, login, JWT issuing (source of truth) |
| **Transaction Service** | 8002 | PostgreSQL (5434) | Transaction CRUD, CSV import, planned transactions, categories |
| **Account Service** | 8004 | PostgreSQL (5436) | Account CRUD, account groups (source of truth) |
| **Categorization Service** | 8005 | PostgreSQL (5435) | Transaction categorization pipeline |
| **Goal Service** | 8006 | PostgreSQL (5438) | Savings goals and goal events |
| **AI Service** | 8007 | ChromaDB | RAG-based financial Q&A (Ollama LLM + vector retrieval) |
| **User Outbox Worker** | — | PostgreSQL (5433) | Polls `outbox_events`, publishes user events to RabbitMQ |
| **Transaction Outbox Worker** | — | PostgreSQL (5434) | Polls `outbox_events`, publishes transaction events to RabbitMQ |
| **Account Outbox Worker** | — | PostgreSQL (5436) | Polls `outbox_events`, publishes account events to RabbitMQ |
| **Goal Outbox Worker** | — | PostgreSQL (5438) | Polls `outbox_events`, publishes goal events to RabbitMQ |
| **UserSync Consumer** | — | MySQL | Sync user data from events to MySQL User table |
| **AccountCreation Consumer** | — | PostgreSQL (5436) | Create default account in Postgres from user.created events |
| **AccountSync Consumer** | — | MySQL | Sync account events from Postgres to MySQL read-replica |
| **CategorySync Consumer** | — | MySQL | Sync categories from transaction-service to MySQL |
| **TransactionSync Consumer** | — | MySQL | Project transaction events into MySQL so analytics/budget/dashboard see microservice writes |

### Future Services (not yet extracted)

| Service | Planned Port | Description |
|---------|-------------|-------------|
| Budget Service | 8003 | Budget management |
| Analytics Service | 8009 | GraphQL gateway + Elasticsearch |
| Notification Service | 8008 | Email/push notifications |
| API Gateway | — | Routing, rate limiting, JWT validation |

---

## Project Structure

```
finance-tracker/
├── services/
│   ├── monolith/                    # Monolith (FastAPI)
│   │   ├── backend/                 # Python package (all imports: backend.*)
│   │   │   ├── main.py              # App, middleware, router registration
│   │   │   ├── config.py            # Environment configuration
│   │   │   ├── auth.py              # JWT auth (creates + validates tokens)
│   │   │   ├── dependencies.py      # FastAPI DI wiring
│   │   │   ├── consumers/           # RabbitMQ event consumers
│   │   │   ├── category/            # Bounded context + categorization pipeline
│   │   │   ├── banking/             # Bank integration (Enable Banking / PSD2)
│   │   │   ├── budget/              # Legacy budget context
│   │   │   ├── monthly_budget/      # Aggregate-based monthly budgets
│   │   │   ├── analytics/           # Dashboard + GraphQL read gateway
│   │   │   │   ├── goal/                # Goals
│   │   │   ├── user/                # Local user management
│   │   │   ├── shared/              # Cross-cutting ports/adapters
│   │   │   ├── models/mysql/        # SQLAlchemy ORM models
│   │   │   └── database/            # Connection managers
│   │   ├── tests/                   # Unit + integration tests
│   │   ├── pyproject.toml
│   │   ├── Makefile
│   │   └── Dockerfile
│   │
│   ├── user-service/                # User microservice
│   │   ├── app/                     # FastAPI app (hexagonal)
│   │   │   └── workers/             # Outbox publisher worker
│   │   ├── migrations/              # Alembic migrations (incl. outbox_events)
│   │   ├── tests/                   # Unit + integration tests
│   │   └── Dockerfile
│   │
│   ├── transaction-service/         # Transaction microservice
│   │   ├── app/                     # FastAPI app (hexagonal + UoW)
│   │   │   └── workers/             # Outbox publisher + categorized consumer
│   │   ├── migrations/              # Alembic migrations (incl. outbox_events)
│   │   ├── tests/                   # Unit + integration tests
│   │   └── Dockerfile
│   │
│   ├── categorization-service/      # Categorization microservice
│   │   ├── app/                     # FastAPI app (hexagonal)
│   │   │   └── workers/             # Outbox publisher + category sync consumer
│   │   ├── migrations/              # Alembic migrations (taxonomy + rules)
│   │   ├── tests/                   # Unit + integration + migration tests
│   │   └── Dockerfile
│   │
│   ├── account-service/              # Account microservice
│   │   ├── app/                     # FastAPI app (hexagonal)
│   │   │   ├── workers/             # Outbox publisher worker
│   │   │   └── consumers/           # Account creation consumer (user.created)
│   │   ├── alembic/                 # Alembic migrations (outbox + partial unique index)
│   │   ├── scripts/                 # Data migration from MySQL
│   │   └── Dockerfile
│   │
│   ├── goal-service/                # Goal microservice
│   │   ├── app/                     # FastAPI app (hexagonal)
│   │   │   └── workers/             # Outbox publisher worker
│   │   ├── migrations/              # Alembic migrations
│   │   ├── tests/                   # Unit + integration tests
│   │   └── Dockerfile
│   │
│   ├── frontend/                    # React SPA (Vite)
│   │   ├── src/
│   │   │   ├── api/                 # REST + GraphQL clients (bank, transactions, etc.)
│   │   │   ├── components/          # UI components (dashboard, bank widget, charts)
│   │   │   ├── pages/               # Page components
│   │   │   ├── context/             # Auth context
│   │   │   ├── hooks/               # Custom hooks (useDashboardData, etc.)
│   │   │   ├── Charts/              # Recharts components (pie, bar, area)
│   │   │   ├── lib/                 # Formatters and utilities
│   │   │   └── utils/               # API client wrapper
│   │   └── package.json
│   │
│   └── shared/
│       └── contracts/               # Shared event schemas (Pydantic)
│           └── contracts/events/    # UserCreated, TransactionCreated, etc.
│
├── tests/
│   └── e2e/                         # End-to-end tests (cross-service)
│
├── Makefile                         # Root orchestration
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
| `POST` | `/api/v1/categories/` | Create category | Yes |
| `GET` | `/api/v1/categories/` | List categories | Yes |
| `GET` | `/api/v1/categories/{id}` | Get category | Yes |
| `PUT` | `/api/v1/categories/{id}` | Update category | Yes |
| `DELETE` | `/api/v1/categories/{id}` | Delete category | Yes |

### Categorization Service (port 8005)

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `POST` | `/api/v1/categorize/` | Sync categorize (tier 1 rule engine) | Internal |

The categorization service also consumes `transaction.created` events for async full-pipeline categorization (rules, ML, LLM, fallback).

### Goal Service (port 8006)

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `POST` | `/api/v1/goals` | Create goal | Yes |
| `GET` | `/api/v1/goals/{id}` | Get goal | Yes |
| `PUT` | `/api/v1/goals/{id}` | Update goal | Yes |
| `DELETE` | `/api/v1/goals/{id}` | Delete goal | Yes |

### Account Service (port 8004)

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `GET` | `/api/v1/accounts/` | List user accounts | Yes |
| `POST` | `/api/v1/accounts/` | Create account | Yes |
| `PUT` | `/api/v1/accounts/{id}` | Update account | Yes |
| `GET` | `/health` | Health check | No |

### AI Service (port 8007)

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `POST` | `/api/v1/ingest` | Embed user's transactions into ChromaDB | Yes |
| `POST` | `/api/v1/chat` | Ask financial questions (RAG) | Yes |
| `GET` | `/health` | Health check | No |

### Monolith (port 8000)

Transactions, planned-transactions and categories are owned by `transaction-service` (port 8002). Accounts are owned by `account-service` (port 8004). The monolith keeps MySQL read-model projections (materialised by sync consumers) but no write endpoints for these resources.

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `*` | `/api/v1/budgets/*` | Legacy budget CRUD | Yes |
| `*` | `/api/v1/monthly-budgets/*` | Monthly budget CRUD + copy | Yes |
| `*` | `/api/v1/dashboard/*` | Analytics | Yes |
| `*` | `/api/v1/goals/*` | Goal CRUD | Yes |
| `*` | `/api/v1/users/*` | User management | Partial |
| `POST` | `/api/v1/graphql` | GraphQL read gateway (reads transactions + categories from projection) | Yes |
| `GET` | `/api/v1/bank/available-banks` | List banks by country | No |
| `POST` | `/api/v1/bank/connect` | Start bank OAuth flow | No |
| `GET` | `/api/v1/bank/callback` | OAuth callback from bank | No |
| `GET` | `/api/v1/bank/connections` | List bank connections | No |
| `POST` | `/api/v1/bank/connections/{id}/sync` | Sync transactions from bank | No |
| `DELETE` | `/api/v1/bank/connections/{id}` | Disconnect bank | No |

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
        RMQ->>ACC: user.created (queue: account_service.account_creation)
        ACC->>PG: INSERT INTO Account (Postgres, source of truth)
    end
```

### Event Catalog

| Event | Producer | Published via | Consumers | Routing Key |
|-------|----------|---------------|-----------|-------------|
| `UserCreatedEvent` | user-service | Outbox worker | UserSyncConsumer, AccountCreationConsumer | `user.created` |
| `TransactionCreatedEvent` | transaction-service | Outbox worker | TransactionSyncConsumer | `transaction.created` |
| `TransactionUpdatedEvent` | transaction-service | Outbox worker | TransactionSyncConsumer | `transaction.updated` |
| `TransactionDeletedEvent` | transaction-service | Outbox worker | TransactionSyncConsumer | `transaction.deleted` |
| `CategoryCreatedEvent` | transaction-service | Outbox worker | CategorySyncConsumer | `category.created` |
| `CategoryUpdatedEvent` | transaction-service | Outbox worker | CategorySyncConsumer | `category.updated` |
| `CategoryDeletedEvent` | transaction-service | Outbox worker | CategorySyncConsumer | `category.deleted` |
| `TransactionCategorizedEvent` | categorization-service | Outbox worker | TransactionCategorizedConsumer | `transaction.categorized` |
| `GoalCreatedEvent` | goal-service | Outbox worker | (future consumers) | `goal.created` |
| `GoalUpdatedEvent` | goal-service | Outbox worker | (future consumers) | `goal.updated` |
| `GoalDeletedEvent` | goal-service | Outbox worker | (future consumers) | `goal.deleted` |
| `AccountCreatedEvent` | account-service | Outbox worker | AccountSyncConsumer | `account.created` |
| `AccountUpdatedEvent` | account-service | Outbox worker | AccountSyncConsumer | `account.updated` |
| `BudgetMonthClosedEvent` | monolith (planned) | Direct publish | Goal-service consumer (planned) | `budget.month_closed` |

### Projecting transactions into MySQL

Historic transactions from `transaction-service` (PostgreSQL) can be replayed into the monolith MySQL read model via a one-off backfill. Run from the repo root with the compose stack running:

```bash
cd services/transaction-service
uv run python ../../scripts/backfill_transaction_projection.py \
    --database-url postgresql+asyncpg://transaction_service:transaction_service_pass@localhost:5434/transactions \
    --rabbitmq-url amqp://guest:guest@localhost:5672/
```

The script iterates over every row in transaction-service and publishes synthetic `transaction.created` events. The running `TransactionSyncConsumer` treats them as upserts, so the script is safe to re-run.

### Transactional Outbox (Event Publishing)

All extracted services (user-service, transaction-service, account-service, goal-service, categorization-service) use the **transactional outbox pattern** to avoid the dual-write problem:

1. Domain data and an `outbox_events` row are written in the **same database transaction**
2. A standalone **outbox worker** polls the table using `SELECT … FOR UPDATE SKIP LOCKED`
3. The worker publishes events to RabbitMQ and marks rows as `published`
4. On publish failure, exponential backoff retries (up to 5 attempts)

This guarantees **at-least-once delivery** — no event is lost even if the application crashes after commit. Downstream consumers must be idempotent.

### Consumer Reliability

All consumers inherit from `BaseConsumer` with:
- **Retry**: 3 attempts with exponential backoff
- **Dead-letter queue**: Failed messages routed to `*.dlq`
- **Idempotency**: DB-backed correlation-ID deduplication via `processed_events` table (survives restarts, auto-cleanup after 7 days)
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
| `ENABLE_BANKING_APP_ID` | monolith | — | Enable Banking application ID |
| `ENABLE_BANKING_KEY_PATH` | monolith | `./enablebanking-sandbox.pem` | Path to PEM private key |
| `ENABLE_BANKING_REDIRECT_URI` | monolith | `http://localhost:8000/api/v1/bank/callback` | OAuth redirect URI |
| `ENABLE_BANKING_ENVIRONMENT` | monolith | `sandbox` | `sandbox` or `production` |

The monolith uses `SECRET_KEY`, microservices use `JWT_SECRET`. Both are set to the same value in docker-compose.

See `example.env` for the full list with descriptions.

---

## Testing

The project has **620+ tests** across all services, organized following the testing pyramid:

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
| Monolith | ~280 | 81 | — | 361 |
| Frontend | 110 | — | — | 110 |
| User Service | 28 | 12 | — | 40 |
| Transaction Service | 61 | 43 | — | 104 |
| Goal Service | ~15 | ~15 | — | ~30 |
| Categorization Service | ~10 | ~5 | — | ~15 |
| Cross-service E2E | — | — | ~15 | ~15 |

### Running Tests

```bash
# All tests via root Makefile
make test

# Monolith tests (335 tests)
cd services/monolith && uv run pytest tests/ -v

# Frontend tests (110 tests)
cd services/frontend && npx vitest run

# User service tests (40 tests)
cd services/user-service && uv run pytest tests/ -v

# Transaction service tests (104 tests)
cd services/transaction-service && uv run pytest tests/ -v

# Goal service tests (~30 tests)
cd services/goal-service && uv run pytest tests/ -v

# Categorization service tests (~15 tests)
cd services/categorization-service && uv run pytest tests/ -v

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
# All services: http://localhost:8000 (monolith), :8001 (user), :8002 (transaction),
#               :8004 (account), :8005 (categorization), :8006 (goal), :8007 (ai)
# RabbitMQ UI: http://localhost:15672 (guest/guest)
# Frontend: http://localhost:3000
```

### Local Development (without Docker)

```bash
# Start infrastructure only
make dev

# Backend (monolith)
cd services/monolith && make dev

# User service
cd services/user-service && make dev

# Transaction service
cd services/transaction-service && make dev

# Categorization service
cd services/categorization-service && make dev

# Goal service
cd services/goal-service && make dev

# Account service
cd services/account-service && make dev

# Consumers (in separate terminals from services/monolith/)
uv run python -m backend.consumers.worker --consumer user-sync
uv run python -m backend.consumers.worker --consumer account-sync
uv run python -m backend.consumers.worker --consumer category-sync
uv run python -m backend.consumers.worker --consumer transaction-sync

# Account creation consumer (from services/account-service/)
python -m app.consumers.worker

# Frontend
cd services/frontend
npm install && npm run dev
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
| [INSTALLATION.md](INSTALLATION.md) | Full setup guide with Docker, seeding, and bank connection |
| [services/monolith/README.md](services/monolith/README.md) | Monolith architecture, router map, banking, categorization |
| [services/monolith/docs/STRUCTURE.md](services/monolith/docs/STRUCTURE.md) | Hexagonal structure map, bounded contexts, SQLAlchemy models |
| [services/frontend/README.md](services/frontend/README.md) | Frontend architecture, dashboard components, design tokens |
| [services/user-service/README.md](services/user-service/README.md) | User service API, events, JWT format |
| [services/transaction-service/README.md](services/transaction-service/README.md) | Transaction service API, UoW pattern, CSV import |
| [services/categorization-service/docs/SCHEMA.md](services/categorization-service/docs/SCHEMA.md) | Categorization service database schema design |
| [services/categorization-service/docs/RETROSPECTIVE.md](services/categorization-service/docs/RETROSPECTIVE.md) | Phase 1 extraction retrospective |
| [services/goal-service/README.md](services/goal-service/README.md) | Goal service API, events, outbox pattern |
| [services/account-service/FOLLOWUPS.md](services/account-service/FOLLOWUPS.md) | Account service follow-ups and migration history |
| [services/ai-service/README.md](services/ai-service/README.md) | AI service RAG architecture, models, and endpoints |
| [services/shared/contracts/README.md](services/shared/contracts/README.md) | Shared event contracts (Pydantic models) |
| [docs/microservice-architecture.mermaid](docs/microservice-architecture.mermaid) | Full architecture diagram (current + future) |
| [services/monolith/DATABASE_COMPARISON.md](services/monolith/DATABASE_COMPARISON.md) | MySQL vs Elasticsearch vs Neo4j comparison |
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
- [x] 620+ tests (unit, integration, frontend, e2e)
- [x] User-service extraction (PostgreSQL, RabbitMQ events)
- [x] Transaction-service extraction (PostgreSQL, UoW, CSV import)
- [x] Event-driven sync (UserSync + AccountCreation consumers)
- [x] Cross-service JWT compatibility
- [x] No cross-service foreign key constraints
- [x] Frontend routing to microservices (categories + transactions via transaction-service, auth via user-service)
- [x] Transactional outbox pattern (at-least-once delivery, dual-write elimination)
- [x] Consumer idempotency store (DB-backed `processed_events` with auto-cleanup)
- [x] Category ownership extracted to transaction-service (with event sync to monolith)
- [x] Cross-service JWT compatibility (unified token format)
- [x] Enable Banking integration (PSD2 Open Banking, OAuth flow, transaction sync)
- [x] Three-level categorization hierarchy (Category, SubCategory, Merchant)
- [x] Multi-tier categorization pipeline (rule engine + ML/LLM ports)
- [x] Dashboard with bank connection widget, trend chart, and tier badges
- [x] Transaction deduplication on bank sync
- [x] TransactionSync projection consumer (transaction.* events → MySQL read model)
- [x] Removed duplicate transaction/planned-transaction bounded context from monolith (single source of truth in transaction-service)
- [x] Banking writes via transaction-service HTTP client — no direct MySQL writes from bank sync
- [x] `POST /api/v1/transactions/bulk` endpoint with server-side dedup on transaction-service
- [x] Categorization-service extraction (rule engine, taxonomy, categorization pipeline as standalone service)
- [x] Hybrid sync/async categorization (sync tier 1 via HTTP, async tier 2/3 via events)
- [x] Rules as data — categorization rules stored in database, not code
- [x] Categorization audit trail (`categorization_results` table)
- [x] Goal-service extraction (CRUD, outbox events, JWT validation)
- [x] ADR-0003: Automatic goal allocation from budget surplus (schema and handler implemented)
- [x] `BudgetMonthClosedEvent` shared contract for cross-service budget close flow
- [x] Positive amount CHECK constraint on transactions and planned_transactions
- [x] TanStack Query for dashboard and transactions (server-state management)
- [x] Radix UI Dialog (accessible modals with focus trap)
- [x] lucide-react icons (replaced emojis with accessible SVG icons)
- [x] Imperative ConfirmDialog provider (replaced `window.confirm`)
- [x] Account-service extraction (outbox, read-replica sync, partial unique index for idempotency)
- [x] AI Service (RAG-based financial Q&A with Ollama + ChromaDB)
- [ ] ML categorizer adapter (train on user-confirmed merchants)
- [ ] LLM categorizer adapter (GPT/Claude for unknown transactions)
- [ ] Budget month close publisher and day-7 scheduled job
- [ ] Goal allocation RabbitMQ consumer (runtime flow for ADR-0003)
- [ ] Frontend support for default savings goal and allocation history
- [ ] API Gateway (routing, rate limiting)
- [ ] Budget service extraction
- [ ] Analytics service + Elasticsearch
