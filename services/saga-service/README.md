# Saga Service

Orchestrates distributed sagas across microservices via RabbitMQ. Phase 1 implements the **bank sync saga** (fetch → import → mark complete with rollback on failure).

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL (port 5440 via docker-compose)
- RabbitMQ (port 5672 via docker-compose)

### Install and run

```bash
cd services/saga-service
make copy-env    # if Makefile.python symlink provides it; else: cp example.env .env
make install-deps
make migrate
make dev
```

Or via docker-compose from the project root:

```bash
docker compose up -d postgres-saga rabbitmq saga-service saga-outbox-worker saga-reply-consumer saga-start-consumer saga-timeout-worker
```

### Health Check

```bash
curl http://localhost:8011/health
# {"status":"healthy","service":"saga-service"}
```

Poll saga status (after starting a bank sync from banking-service):

```bash
# Via gateway (browser / frontend — requires JWT)
curl -H "Authorization: Bearer $TOKEN" http://localhost:8010/api/v1/sagas/{saga_id}

# Direct to saga-service (internal / debugging only)
curl http://localhost:8011/api/v1/sagas/{saga_id}
```

## Architecture

```text
app/
├── main.py                 # FastAPI: health + GET /api/v1/sagas/{id}
├── application/
│   ├── orchestrator.py     # Generic saga engine (start, reply, compensate, timeout)
│   └── sagas/              # Saga definitions (bank_sync_saga.py)
├── domain/                 # SagaInstance, SagaStatus, SagaDefinition
├── adapters/outbound/      # Postgres repos, RabbitMQ publisher, UoW
└── workers/
    ├── outbox_publisher.py       # Publishes saga commands from outbox
    ├── saga_start_consumer.py    # Consumes saga.*.start events
    ├── saga_reply_consumer.py    # Consumes saga.reply.* from participants
    └── saga_timeout_worker.py    # Marks stale sagas as timed_out
```

### Bank sync flow

```mermaid
sequenceDiagram
    participant FE as Frontend
    participant Bank as banking-service
    participant Outbox as banking outbox
    participant Start as saga-start-consumer
    participant Orch as SagaOrchestrator
    participant BankW as banking-saga-command-consumer
    participant TxW as transaction-saga-command-consumer

    FE->>Bank: POST /connections/{id}/sync
    Bank-->>FE: 202 { saga_id }
    Bank->>Outbox: BankSyncSagaStartEvent
    Outbox->>Start: saga.bank_sync.start
    Start->>Orch: start_saga(bank_sync)
    Orch->>BankW: saga.cmd.bank_fetch_transactions
    BankW-->>Orch: saga.reply.fetch_transactions
    Orch->>TxW: saga.cmd.bulk_import_transactions
    TxW-->>Orch: saga.reply.import_transactions
    Orch->>BankW: saga.cmd.mark_sync_complete
    BankW-->>Orch: saga.reply.mark_sync_complete
    FE->>Orch: GET /sagas/{saga_id} (poll)
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `make install-deps` | Install dependencies with uv |
| `make dev` | Start API on port 8011 with reload |
| `make check` | Run lint + format checks |
| `make test` | Run unit tests |
| `make migrate` | Run Alembic migrations |
| `make migrate-down` | Roll back one migration |

## Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | sqlite in-memory | PostgreSQL connection string |
| `RABBITMQ_URL` | Yes | `amqp://guest:guest@rabbitmq:5672/` | RabbitMQ broker |
| `CORS_ORIGINS` | No | localhost:3000,3001 | Allowed CORS origins |
| `SAGA_TIMEOUT_SECONDS` | No | `300` | Max age before saga is timed out |
| `TIMEOUT_CHECK_INTERVAL_SECONDS` | No | `30` | Timeout worker poll interval |
| `ENVIRONMENT` | No | `development` | Runtime environment |

See `example.env` for all options.

## Testing

```bash
make test
```

Unit tests cover the orchestrator (advance, compensate, timeouts) and saga start event parsing.
