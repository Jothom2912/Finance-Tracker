# Goal Service

Standalone microservice for managing financial goals and savings targets. Uses PostgreSQL with `NUMERIC(12,2)` for exact decimal arithmetic.

This service follows hexagonal architecture with clear separation between domain, application, and adapter layers. Domain events are published via RabbitMQ for integration with other services.

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL (port 5434 via docker-compose)
- RabbitMQ (port 5672 via docker-compose)

### Install and run

```bash
cd services/goal-service
uv sync --dev
uv run uvicorn app.main:app --host 0.0.0.0 --port 8003 --reload
```

Or via docker-compose from the project root:

```bash
docker compose up goal-service
```

### Health Check

```bash
curl http://localhost:8003/health
# {"status": "healthy", "service": "goal-service"}
```

## Architecture

```text
app/
├── main.py                 # FastAPI app, lifespan, CORS, exception handlers
├── config.py               # Pydantic BaseSettings (env vars)
├── domain/
│   ├── entities.py         # Goal (frozen dataclass)
│   └── exceptions.py       # GoalException, GoalNotFound, AccountNotFoundForGoal
├── application/
│   ├── service.py          # GoalService (core business logic)
│   ├── dto.py              # Pydantic schemas for API
│   └── ports/
│       ├── inbound.py      # IGoalService (service interface)
│       └── outbound.py     # IGoalRepository, IAccountPort
└── adapters/
    ├── inbound/
    │   └── goal_api.py     # FastAPI routes for Goals
    └── outbound/
        ├── postgres_goal_repository.py  # PostgreSQL Goal repository
        └── account_adapter.py           # Anti-corruption layer for Account service
```

## Features

- **Goal Management**: Create, read, update, delete financial goals
- **Progress Tracking**: Calculate goal progress as percentage and completion status
- **Account Integration**: Goals tied to user accounts with validation
- **Validation**: Comprehensive validation using Pydantic schemas with boundary value analysis (BVA)
- **Error Handling**: Clear domain exceptions for business rule violations

## API Endpoints

### Create Goal
```bash
POST /goals
Content-Type: application/json

{
  "name": "Summer Vacation",
  "target_amount": 5000.00,
  "current_amount": 1000.00,
  "target_date": "2024-07-01",
  "status": "active",
  "Account_idAccount": 1
}
```

### List Goals
```bash
GET /goals?account_id=1
```

### Get Goal
```bash
GET /goals/{goal_id}
```

### Update Goal
```bash
PUT /goals/{goal_id}
Content-Type: application/json

{
  "name": "Updated Goal",
  "target_amount": 6000.00,
  "current_amount": 2000.00,
  "target_date": "2024-08-01",
  "status": "active"
}
```

### Delete Goal
```bash
DELETE /goals/{goal_id}
```

## Development

### Run tests
```bash
make test                # Fast suite (unit + integration)
make test-unit          # Unit tests only
make test-integration   # Integration tests only
make test-migrations    # Migration tests (requires Docker)
make test-all           # All tests including slow Testcontainers
```

### Code quality
```bash
make lint               # Run ruff linter
make format             # Auto-format code
make format-check       # Check formatting without changes
make check              # Run all quality checks
```

### Database migrations
```bash
make migrate            # Run migrations to latest
make migrate-down       # Rollback last migration
```

## Environment Variables

See `example.env` for all required variables:

```
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5434/goal_service
RABBITMQ_URL=amqp://guest:guest@localhost:5672/
JWT_SECRET=your-secret-key
JWT_ALGORITHM=HS256
CORS_ORIGINS=http://localhost:3000,http://localhost:3001
ENVIRONMENT=development
LOG_LEVEL=INFO
```

## Design Patterns

### Hexagonal Architecture
- **Domain**: Pure business logic, no dependencies
- **Application**: Use cases orchestrating domain and infrastructure
- **Adapters**: External system integration (API, database, services)

### Dependency Injection
All external dependencies injected via constructors for testability.

### Ports & Adapters
- **Inbound ports**: Define what the service can do (IGoalService)
- **Outbound ports**: Define external dependencies (IGoalRepository, IAccountPort)

## Known Limitations

- Account validation currently mocked - connects to user-service in production
- Goal projections not yet implemented - for analytics service integration
