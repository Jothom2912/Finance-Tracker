# User Service

Standalone microservice for user registration, authentication, and JWT token issuing. This is the **source of truth** for user identity — all other services validate tokens but do not issue them.

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL (port 5433 via docker-compose)
- RabbitMQ (port 5672 via docker-compose)

### Install and run

```bash
cd services/user-service
uv sync --dev
uv run uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

Or via docker-compose from the project root:

```bash
docker compose up user-service
```

### Health Check

```bash
curl http://localhost:8001/health
# {"status": "healthy", "service": "user-service"}
```

## Architecture

```text
app/
├── main.py              # FastAPI app, lifespan, CORS, exception handlers
├── config.py            # Pydantic BaseSettings (env vars)
├── auth.py              # JWT creation + validation, bcrypt hashing
├── database.py          # Async SQLAlchemy engine + session factory
├── models.py            # PostgreSQL ORM models (UserModel, OutboxEventModel)
├── domain/
│   ├── entities.py      # User, UserWithCredentials (frozen dataclasses)
│   └── exceptions.py    # DuplicateEmailException, InvalidCredentialsException
├── application/
│   ├── ports/
│   │   ├── inbound.py   # IUserService interface
│   │   └── outbound.py  # IUserRepository, IOutboxRepository, IUnitOfWork interfaces
│   ├── dto.py           # RegisterDTO, LoginDTO, TokenResponse
│   └── service.py       # UserService (register, login, get_user) with UoW
├── adapters/
│   ├── inbound/
│   │   └── rest_api.py  # FastAPI router (/api/v1/users/*)
│   └── outbound/
│       ├── postgres_user_repository.py
│       ├── postgres_outbox_repository.py
│       ├── unit_of_work.py  # SQLAlchemyUnitOfWork (shared session)
│       └── rabbitmq_publisher.py
├── workers/
│   └── outbox_publisher.py  # Polls outbox, publishes to RabbitMQ
├── dependencies.py      # FastAPI DI wiring
├── alembic.ini          # Database migrations
└── migrations/          # Alembic migration versions
```

## API Endpoints

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `POST` | `/api/v1/users/register` | Register new user | No |
| `POST` | `/api/v1/users/login` | Login (returns JWT) | No |
| `GET` | `/api/v1/users/me` | Get current user profile | Yes |
| `GET` | `/health` | Health check | No |

### Register

```bash
curl -X POST http://localhost:8001/api/v1/users/register \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "email": "alice@example.com", "password": "SecurePass123!"}'
```

### Login

```bash
curl -X POST http://localhost:8001/api/v1/users/login \
  -H "Content-Type: application/json" \
  -d '{"username_or_email": "alice@example.com", "password": "SecurePass123!"}'
```

Returns `{"access_token": "...", "token_type": "bearer", "user_id": 1, "username": "alice"}`.

The `username_or_email` field accepts either username or email. If it contains `@`, it looks up by email, otherwise by username.

## Event Publishing (Transactional Outbox)

On successful registration, the service writes a `UserCreatedEvent` to the `outbox_events` table in the same database transaction as the user. A standalone outbox worker polls the table and publishes to RabbitMQ, guaranteeing at-least-once delivery:

```json
{
  "event_type": "user.created",
  "event_version": 1,
  "user_id": 6,
  "email": "alice@example.com",
  "username": "alice",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2026-03-11T10:00:00+00:00"
}
```

This event is consumed by:
- **UserSyncConsumer** (monolith) — syncs user to MySQL
- **AccountCreationConsumer** (monolith) — creates a default account

## JWT Format

Tokens contain:
- `sub`: user ID as string (standard JWT claim)
- `user_id`: user ID as integer (monolith compatibility)
- `username`: username string (monolith compatibility)
- `email`: email string (monolith compatibility)
- `exp`: expiration timestamp

All services (monolith, transaction-service) validate tokens using the same shared `JWT_SECRET`. The token includes both `sub` (standard) and `user_id`/`username`/`email` (legacy) claims to ensure cross-service compatibility during the migration from monolith to microservices.

## Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | — | PostgreSQL async connection string |
| `RABBITMQ_URL` | No | `amqp://guest:guest@localhost:5672/` | RabbitMQ connection |
| `JWT_SECRET` | Yes | — | JWT signing key (must match across services) |
| `JWT_ALGORITHM` | No | `HS256` | JWT algorithm |
| `JWT_EXPIRE_MINUTES` | No | `60` | Token expiration in minutes |
| `CORS_ORIGINS` | No | `http://localhost:3000,http://localhost:3001` | Allowed origins |
| `ENVIRONMENT` | No | `development` | Runtime environment |

## Testing

```bash
# Unit tests (28 tests — service logic, DTO BVA, outbox publisher)
uv run pytest tests/unit/ -v

# Integration tests (12 tests — full HTTP flow with SQLite, JWT compatibility)
uv run pytest tests/integration/ -v

# All tests (40 total)
uv run pytest tests/ -v
```

## Database

- **Engine**: PostgreSQL 16 (async via `asyncpg`)
- **ORM**: SQLAlchemy 2.0 async
- **Migrations**: Alembic
- **Port**: 5433 (host) → 5432 (container) in docker-compose
