# Budget Service

Budget management microservice handling budgets and monthly budget summaries.

## Port

```
8003 (host) → 8003 (container)
```

## Quick Start

```bash
cd services/budget-service
make install-deps
make dev
```

Or via Docker Compose:

```bash
docker compose up budget-service -d
```

## Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/budgets/` | JWT | List budgets for account |
| `POST` | `/api/v1/budgets/` | JWT | Create budget |
| `GET` | `/api/v1/monthly-budgets/summary` | JWT | Monthly budget summary |
| `GET` | `/health` | None | Health check |

## Database

PostgreSQL on port 5437 (`budget_service` / `budget_service`).
