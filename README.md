# Finance Tracker — Microservices Personal Finance Application

A personal finance tracking application built as event-driven microservices. The backend uses FastAPI with hexagonal architecture (ports & adapters), CQRS-lite (REST writes, GraphQL reads via gateway-service), event-driven communication via RabbitMQ, and PostgreSQL database-per-service. Includes live bank integration via Enable Banking (PSD2 Open Banking) with distributed saga orchestration for bank sync, automatic transaction categorization through a multi-tier pipeline (rule engine live; ML/LLM tiers prepared), and a streaming AI chat assistant powered by Ollama and ChromaDB.

The legacy Django/MySQL monolith (`services/monolith/`) is no longer part of the runtime stack — all reads go through gateway-service (port 8010).

## Table of Contents

- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Bank Integration](#bank-integration)
- [Distributed Sagas](#distributed-sagas)
- [Categorization Pipeline](#categorization-pipeline)
- [AI Chat Pipeline](#ai-chat-pipeline)
- [Service Map](#service-map)
- [Project Structure](#project-structure)
- [API Reference](#api-reference)
- [Event-Driven Architecture](#event-driven-architecture)
- [Configuration](#configuration)
- [Monitoring](#monitoring)
- [Testing](#testing)
- [Development](#development)

---

## Quick Start

### Prerequisites

- Python 3.11+
- `uv` (Python package manager)
- Node.js 18+ and `yarn` (for frontend)
- Docker Desktop

### Start everything

```bash
docker compose up -d
```

This starts all services:

| Service | Port | Description |
|---------|------|-------------|
| PostgreSQL (users) | 5433 | User-service database |
| PostgreSQL (transactions) | 5434 | Transaction-service database |
| PostgreSQL (categorization) | 5435 | Categorization-service database |
| PostgreSQL (accounts) | 5436 | Account-service database |
| PostgreSQL (budgets) | 5437 | Budget-service database |
| PostgreSQL (goals) | 5438 | Goal-service database |
| PostgreSQL (banking) | 5439 | Banking-service database |
| PostgreSQL (saga) | 5440 | Saga-service database |
| RabbitMQ | 5672 / 15672 | Event bus + management UI |
| Redis | 6380 | Cache for transaction/budget services |
| Ollama | 11435 | Local LLM runtime (qwen3 + bge-m3) |
| User Service | 8001 | Registration, login, JWT issuing |
| Transaction Service | 8002 | Transaction CRUD, CSV import, planned transactions |
| Budget Service | 8003 | Budget management, monthly summaries |
| Account Service | 8004 | Account CRUD, account groups |
| Categorization Service | 8005 | Rule/ML/LLM categorization pipeline |
| Goal Service | 8006 | Savings goals, budget surplus allocation |
| AI Service | 8007 | Streaming financial Q&A (Ollama + ChromaDB) |
| Banking Service | 8009 | PSD2 bank integration (Enable Banking) |
| Gateway Service | 8010 | Dashboard REST + GraphQL reads (BFF) |
| Saga Service | 8011 | Distributed saga orchestration (bank sync) |

**Wait 30–60 seconds** for health checks to pass. The `ollama-pull` init container downloads `qwen3:4b` and `bge-m3` on first start.

### Frontend

```bash
cd services/frontend
yarn install
yarn dev
```

App: http://localhost:3000

### Verify services

```bash
curl http://localhost:8001/health   # User Service
curl http://localhost:8002/health   # Transaction Service
curl http://localhost:8003/health   # Budget Service
curl http://localhost:8004/health   # Account Service
curl http://localhost:8005/health   # Categorization Service
curl http://localhost:8006/health   # Goal Service
curl http://localhost:8007/health   # AI Service
curl http://localhost:8009/health   # Banking Service
curl http://localhost:8010/health   # Gateway Service
curl http://localhost:8011/health   # Saga Service
```

---

## Architecture

### System Overview

The application is a fully decomposed microservices architecture. Each bounded context owns its data (database-per-service) and communicates via events through RabbitMQ. Long-running cross-service flows (bank sync) use the saga-service for orchestration with compensation on failure.

```mermaid
graph LR
    FE[React Frontend] -->|register/login| US[User Service<br/>:8001]
    FE -->|transactions| TS[Transaction Service<br/>:8002]
    FE -->|accounts| AS[Account Service<br/>:8004]
    FE -->|budgets| BS[Budget Service<br/>:8003]
    FE -->|goals| GS[Goal Service<br/>:8006]
    FE -->|dashboard, GraphQL| GW[Gateway Service<br/>:8010]
    FE -->|bank connect| BANK[Banking Service<br/>:8009]
    FE -->|AI chat| AI[AI Service<br/>:8007]
    FE -->|saga status| GW

    GW -->|saga poll| SAGA[Saga Service<br/>:8011]

    US -->|"write + outbox"| PG_U[(PostgreSQL<br/>Users)]
    TS -->|"write + outbox"| PG_T[(PostgreSQL<br/>Transactions)]
    AS -->|"write + outbox"| PG_A[(PostgreSQL<br/>Accounts)]
    BS -->|"write + outbox"| PG_B[(PostgreSQL<br/>Budgets)]
    GS -->|"write + outbox"| PG_G[(PostgreSQL<br/>Goals)]
    BANK -->|"write + outbox"| PG_BK[(PostgreSQL<br/>Banking)]
    SAGA -->|"orchestration + outbox"| PG_S[(PostgreSQL<br/>Sagas)]
    CS[Categorization Service<br/>:8005] -->|"categorize + outbox"| PG_C[(PostgreSQL<br/>Categorization)]

    TS -->|"sync categorize<br/>(HTTP)"| CS
    GW -->|"fan-out reads"| TS
    GW -->|"fan-out reads"| AS
    GW -->|"fan-out reads"| BS
    AI -->|"analytics data"| GW
    AI --> OLL[Ollama<br/>:11435]

    PG_U -->|poll| UOW[Outbox Workers]
    PG_T -->|poll| UOW
    PG_A -->|poll| UOW
    PG_B -->|poll| UOW
    PG_G -->|poll| UOW
    PG_BK -->|poll| UOW
    PG_C -->|poll| UOW
    PG_S -->|poll| UOW

    UOW -->|publish| RMQ[RabbitMQ]

    RMQ -->|user.created| ASC[Account Service<br/>Consumer]
    RMQ -->|transaction.created| CS
    RMQ -->|transaction.categorized| TCC[Categorized<br/>Consumer]
    RMQ -->|category.*| CCSC[Cat-Service<br/>Category Sync]
    RMQ -->|budget.month_closed| GBC[Goal Budget<br/>Consumer]
    RMQ -->|account.*| BAPC[Banking Account<br/>Projection]
    RMQ -->|saga.*| SAGA
    SAGA -->|saga.cmd.*| BANK
    SAGA -->|saga.cmd.*| TS

    ASC -->|INSERT Account| PG_A
```

### Key Architecture Decisions

| Decision | Rationale |
|----------|-----------|
| **PostgreSQL-only** | All active services use PostgreSQL. NUMERIC type for money, async drivers |
| **Database-per-service** | No cross-service DB access, only events and HTTP between bounded contexts |
| **Event-driven sync** | `user.created` triggers default account creation; `transaction.created` triggers categorization |
| **Shared JWT secret** | All services validate tokens with the same secret. User-service is the sole token issuer |
| **Transactional outbox** | Domain data and event written in same DB transaction. Worker polls with `SELECT ... FOR UPDATE SKIP LOCKED` |
| **Gateway as BFF** | `gateway-service` fans out to multiple services for dashboard/analytics reads and saga status |
| **REST for mutations, GraphQL for reads** | Writes via REST on domain services; nested dashboard reads via GraphQL on gateway |
| **Distributed sagas** | Bank sync orchestrated by saga-service with compensation (rollback import on failure) |
| **Multi-tier categorization** | Rule engine first (fast, deterministic), then ML/LLM (expensive, probabilistic) |
| **PSD2 via Enable Banking** | Aggregator abstracts bank-specific APIs; JWT-signed requests; OAuth for user consent |
| **Monolith retired** | MySQL monolith and sync consumers removed; gateway-service is the sole read aggregation layer |

### Hexagonal Architecture (per service)

Each bounded context follows the same structure:

```text
adapters/
├── inbound/       # REST API controllers
└── outbound/      # Repository implementations, event publishers, HTTP clients
application/
├── ports/         # Inbound + outbound interfaces (ABC)
├── service.py     # Application service (business rules)
└── dto.py         # Pydantic DTOs
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
| Saga status | REST (via gateway) | `GET /api/v1/sagas/{saga_id}` |

---

## Bank Integration

The banking-service connects to real bank accounts via [Enable Banking](https://enablebanking.com/) using the PSD2 Open Banking standard. Bank sync is orchestrated as a distributed saga (see [Distributed Sagas](#distributed-sagas)).

```mermaid
sequenceDiagram
    participant User as User / Browser
    participant API as Banking Service
    participant EB as Enable Banking
    participant Bank as Bank (Nordea etc.)
    participant Saga as Saga Service
    participant Tx as Transaction Service

    User->>API: POST /bank/connect
    API->>EB: Create authorization URL
    EB-->>API: Authorization URL + state
    API-->>User: Redirect to bank

    User->>Bank: Authorize via bank login
    Bank-->>API: GET /bank/callback?code=xxx

    API->>EB: Create session (exchange code)
    EB-->>API: Session ID + accounts
    API->>API: Store BankConnection records

    User->>API: POST /bank/connections/{id}/sync
    API-->>User: 202 { saga_id }
    API->>Saga: saga.bank_sync.start (via outbox)

    Saga->>API: saga.cmd.bank_fetch_transactions
    API->>EB: Fetch transactions
    EB-->>API: Raw transactions
    API-->>Saga: saga.reply.fetch_transactions

    Saga->>Tx: saga.cmd.bulk_import_transactions
    Tx->>Tx: Dedupe + persist + outbox events
    Tx-->>Saga: saga.reply.import_transactions

    Saga->>API: saga.cmd.mark_sync_complete
    API-->>Saga: saga.reply.mark_sync_complete

    User->>Saga: GET /sagas/{saga_id} (poll via gateway)
```

---

## Distributed Sagas

The saga-service (port 8011) orchestrates multi-step workflows across services via RabbitMQ command/reply events. Phase 1 implements the **bank sync saga**: fetch transactions → bulk import → mark sync complete, with rollback on failure.

| Worker | Role |
|--------|------|
| `saga-start-consumer` | Starts saga instances on `saga.*.start` events |
| `saga-reply-consumer` | Advances saga on participant replies |
| `saga-outbox-worker` | Publishes saga commands from outbox |
| `saga-timeout-worker` | Marks stale sagas as timed out |
| `banking-saga-command-consumer` | Executes banking-side saga steps |
| `transaction-saga-command-consumer` | Executes transaction-side saga steps (bulk import, rollback) |

Poll saga status from the frontend via gateway:

```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8010/api/v1/sagas/{saga_id}
```

See `services/saga-service/README.md` for full saga architecture details.

---

## Categorization Pipeline

Transactions are categorized through a multi-tier orchestrator:

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

The rule engine tier is live. ML and LLM tiers are implemented but not yet wired in production paths.

---

## AI Chat Pipeline

The AI service exposes a 3-step streaming SSE pipeline for financial Q&A:

```mermaid
flowchart LR
    Q[User question] --> R[Router<br/>qwen3:4b]
    R --> D[Dispatcher<br/>fetch data]
    D --> P[Responder<br/>qwen3:8b]
    P --> SSE[SSE stream to client]
    D --> CDB[(ChromaDB<br/>semantic search)]
    D --> GW[Gateway / Transaction services]
```

| Endpoint | Description |
|----------|-------------|
| `POST /api/v1/chat/stream` | SSE streaming chat (JWT required) |
| `POST /api/v1/ingest` | Embed user transactions into ChromaDB |
| `GET /health` | Health check |

See `services/ai-service/README.md` for model configuration and intent types.

---

## Service Map

| Service | Port | Database | Role |
|---------|------|----------|------|
| **User Service** | 8001 | PostgreSQL (5433) | User registration, login, JWT issuing |
| **Transaction Service** | 8002 | PostgreSQL (5434) | Transaction CRUD, CSV import, planned transactions, categories |
| **Budget Service** | 8003 | PostgreSQL (5437) | Budgets, monthly budget summaries |
| **Account Service** | 8004 | PostgreSQL (5436) | Account CRUD, account groups |
| **Categorization Service** | 8005 | PostgreSQL (5435) | Transaction categorization pipeline |
| **Goal Service** | 8006 | PostgreSQL (5438) | Savings goals, budget surplus allocation |
| **AI Service** | 8007 | ChromaDB (volume) | Streaming financial Q&A (Ollama + ChromaDB) |
| **Banking Service** | 8009 | PostgreSQL (5439) | PSD2 bank integration (Enable Banking) |
| **Gateway Service** | 8010 | — (fans out) | Dashboard REST + GraphQL BFF |
| **Saga Service** | 8011 | PostgreSQL (5440) | Distributed saga orchestration |

### Planned / Stub Services

| Service | Port | Status |
|---------|------|--------|
| **Analytics Service** | 8007 (reserved) | Stub — reads handled by gateway-service |
| **Notification Service** | 8008 | Planned — budget threshold and goal event notifications |

### Workers & Consumers

| Worker | Role |
|--------|------|
| User Outbox Worker | Publishes user events to RabbitMQ |
| Transaction Outbox Worker | Publishes transaction events to RabbitMQ |
| Account Outbox Publisher | Publishes account events to RabbitMQ |
| Account Service Consumer | Creates default account on `user.created` |
| Budget Outbox Worker | Publishes budget events to RabbitMQ |
| Categorization Outbox Worker | Publishes categorization events to RabbitMQ |
| Goal Outbox Worker | Publishes goal events to RabbitMQ |
| Banking Outbox Worker | Publishes banking events to RabbitMQ |
| Saga Outbox Worker | Publishes saga commands to RabbitMQ |
| Transaction Categorized Consumer | Writes categorization results back to transaction-service |
| Categorization Category Sync | Syncs categories from transaction-service |
| Categorization Transaction Consumer | Triggers async categorization on `transaction.created` |
| Goal Budget Consumer | Handles `budget.month_closed` events (surplus → default goal) |
| Banking Account Projection | Projects account events into banking-service |
| Saga Start / Reply / Timeout Workers | Saga lifecycle management |
| Banking / Transaction Saga Command Consumers | Execute saga steps in participating services |

---

## Project Structure

```text
Finance-Tracker/
├── services/
│   ├── user-service/           # Auth, registration, JWT
│   ├── transaction-service/    # Transactions, CSV import, saga participant
│   ├── budget-service/         # Budgets, monthly summaries
│   ├── account-service/        # Accounts, account groups
│   ├── categorization-service/ # Rule/ML/LLM categorization
│   ├── goal-service/           # Savings goals, budget surplus allocation
│   ├── ai-service/             # Streaming Q&A (Ollama + ChromaDB)
│   ├── banking-service/        # PSD2 bank integration, saga participant
│   ├── gateway-service/        # Dashboard BFF (GraphQL + REST)
│   ├── saga-service/           # Distributed saga orchestration
│   ├── frontend/               # React + Vite SPA
│   ├── shared/                 # Event contracts + auth lib
│   ├── analytics-service/      # Stub (reads via gateway)
│   ├── notification-service/   # Planned
│   ├── monolith/               # Legacy Django app (not in docker-compose)
│   └── serverless-health-job/  # KEDA health monitor
├── k8s/                        # Kubernetes manifests (Kustomize + monitoring)
├── monitoring/                 # Prometheus/Grafana/Loki configs (local overlay)
├── tests/e2e/                  # End-to-end tests
├── scripts/                    # Dev/ops utility scripts
├── docs/                       # ADRs, assignment reports
├── docker-compose.yml          # Local development stack
├── docker-compose.monitoring.yml  # Optional monitoring overlay
└── Makefile                    # Orchestration targets
```

---

## API Reference

Each service exposes versioned REST endpoints under `/api/v1/`. OpenAPI docs are available at `/docs` on each FastAPI service when running locally.

| Service | Key endpoints |
|---------|---------------|
| User | `POST /api/v1/auth/register`, `POST /api/v1/auth/login` |
| Transaction | `GET/POST /api/v1/transactions/`, `POST /api/v1/transactions/import-csv` |
| Account | `GET/POST /api/v1/accounts/`, `GET/POST /api/v1/account-groups/` |
| Budget | `GET/POST /api/v1/budgets/`, `GET /api/v1/monthly-budgets/summary` |
| Goal | `GET/POST /api/v1/goals/` |
| Banking | `POST /api/v1/bank/connect`, `POST /api/v1/bank/connections/{id}/sync` |
| Gateway | `GET /api/v1/dashboard/`, `POST /api/v1/graphql`, `GET /api/v1/sagas/{id}` |
| AI | `POST /api/v1/chat/stream` (SSE), `POST /api/v1/ingest` |
| Saga | `GET /api/v1/sagas/{id}` (internal; prefer gateway for authenticated access) |

GraphQL schema is served by gateway-service at `/api/v1/graphql` (Strawberry).

---

## Event-Driven Architecture

### Exchange & Routing

All services publish to a single topic exchange: `finans_tracker.events`

| Routing Key | Publisher | Consumers |
|-------------|-----------|-----------|
| `user.created` | user-service | account-service-consumer |
| `transaction.created` | transaction-service | categorization-transaction-consumer |
| `transaction.categorized` | categorization-service | transaction-categorized-consumer |
| `category.*` | transaction-service | categorization-category-sync |
| `account.*` | account-service | banking-account-projection-consumer |
| `budget.month_closed` | budget-service | goal-budget-consumer |
| `saga.bank_sync.start` | banking-service | saga-start-consumer |
| `saga.cmd.*` | saga-service (via outbox) | banking/transaction saga command consumers |
| `saga.reply.*` | participating services | saga-reply-consumer |

### Outbox Pattern

Each service writes domain events to an `outbox_events` table in the same transaction as the domain write. A dedicated outbox worker polls with `SELECT ... FOR UPDATE SKIP LOCKED` and publishes to RabbitMQ, ensuring at-least-once delivery without dual-write problems. Consumers are idempotent via DB-backed `processed_events` tables.

---

## Configuration

### Environment Variables

See `example.env` for all available options.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SECRET_KEY` / `JWT_SECRET` | Yes | — | JWT secret for token signing (shared across services) |
| `INTERNAL_API_KEY` | Yes (inter-service) | — | Service-to-service authentication |
| `ENVIRONMENT` | No | development | development/staging/production |
| `CORS_ORIGINS` | No | localhost:3000 | Allowed CORS origins |
| `ENABLE_BANKING_APP_ID` | For banking | — | Enable Banking app ID |
| `ENABLE_BANKING_KEY_PATH` | For banking | — | Path to PEM private key |
| `SAGA_SERVICE_URL` | Gateway | `http://saga-service:8011` | Saga service URL |
| `SAGA_TIMEOUT_SECONDS` | No | 300 | Max saga duration before timeout |
| `OLLAMA_BASE_URL` | AI service | `http://ollama:11434` | Ollama server URL |

Each service reads its own `DATABASE_URL` from the environment (set in `docker-compose.yml`).

Copy the template before local development:

```bash
cp example.env .env
```

---

## Monitoring

An optional local monitoring stack (Prometheus, Grafana, Loki, Promtail) is available via compose overlay:

```bash
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d
```

| Service | Port | Description |
|---------|------|-------------|
| Prometheus | 9090 | Metrics collection |
| Grafana | 3001 | Dashboards (admin/admin) |
| Loki | 3100 | Log aggregation |

Production-style manifests with the same stack live under `k8s/monitoring/`.

---

## Testing

```bash
# Run all service tests
make test

# Run E2E tests (requires docker compose up)
make test-e2e

# Run tests for a specific service
make -C services/user-service test
make -C services/saga-service test
```

The project has 650+ automated tests (~490 Python across microservices and e2e, ~170 frontend Vitest).

---

## Development

### CLI Commands

| Command | Description |
|---------|-------------|
| `make install-deps` | Install deps for all services |
| `make dev` | Start infra, print instructions |
| `make dev-docker` | Start everything in Docker |
| `make down` | Stop all Docker containers |
| `make logs` | Tail Docker container logs |
| `make build` | Build all Docker images |
| `make test` | Run all tests |
| `make test-e2e` | Run E2E tests |
| `make lint` | Run ruff on all Python services |
| `make format` | Auto-format all Python services |
| `make check` | Run all quality checks |

Per-service development (infra must be running via `make dev` or `docker compose up -d`):

| Command | Port |
|---------|------|
| `make dev-user-service` | 8001 |
| `make dev-transaction-service` | 8002 |
| `make dev-budget-service` | 8003 |
| `make dev-account-service` | 8004 |
| `make dev-categorization-service` | 8005 |
| `make dev-goal-service` | 8006 |
| `make dev-frontend` | 3000 |

### Frontend development

```bash
cd services/frontend
yarn install
yarn dev
```

### Adding a new service

1. Create `services/<name>/` with hexagonal structure
2. Add PostgreSQL instance to `docker-compose.yml`
3. Add outbox worker if the service publishes events
4. Add shared event contracts to `services/shared/contracts/`
5. Add K8s manifest to `k8s/apps/` and workers to `k8s/workers/`
6. Bootstrap from an existing service (e.g. account-service) — match env.py, config, and Docker setup patterns
