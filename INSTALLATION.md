# Installation Guide — Finance Tracker

## Prerequisites

- **Docker Desktop** installed and running
- **Git** installed
- **Node.js 18+** and **yarn** (for frontend)
- **Python 3.11+** and **uv** (for local development)
- **4GB RAM** available

---

## Quick Start

### 1. Clone Repository

```bash
git clone https://github.com/jothom2912/finance-tracker.git
cd finance-tracker
```

### 2. Start All Services

```bash
docker compose up -d
```

This starts all microservices, databases, and infrastructure:

| Service | Port | Description |
|---------|------|-------------|
| **PostgreSQL (users)** | 5433 | User-service database |
| **PostgreSQL (transactions)** | 5434 | Transaction-service database |
| **PostgreSQL (categorization)** | 5435 | Categorization-service database |
| **PostgreSQL (accounts)** | 5436 | Account-service database |
| **PostgreSQL (budgets)** | 5437 | Budget-service database |
| **PostgreSQL (goals)** | 5438 | Goal-service database |
| **PostgreSQL (banking)** | 5439 | Banking-service database |
| **RabbitMQ** | 5672 / 15672 | Event bus + management UI |
| **Redis** | 6379 | Cache |
| **User Service** | 8001 | Registration, login, JWT issuing |
| **Transaction Service** | 8002 | Transaction CRUD, CSV import |
| **Budget Service** | 8003 | Budgets, monthly summaries |
| **Account Service** | 8004 | Account CRUD, account groups |
| **Categorization Service** | 8005 | Rule/ML/LLM categorization pipeline |
| **Goal Service** | 8006 | Savings goals |
| **AI Service** | 8007 | RAG-based financial Q&A |
| **Banking Service** | 8009 | PSD2 bank integration |
| **Gateway Service** | 8010 | Dashboard REST + GraphQL BFF |

Plus outbox workers and event consumers for each service.

**Wait 30-60 seconds** for all health checks to pass.

### 3. Start Frontend

```bash
cd services/frontend
yarn install
yarn dev
```

Open http://localhost:3000

### 4. Verify services

```bash
curl http://localhost:8001/health   # User Service
curl http://localhost:8002/health   # Transaction Service
curl http://localhost:8003/health   # Budget Service
curl http://localhost:8004/health   # Account Service
curl http://localhost:8005/health   # Categorization Service
curl http://localhost:8006/health   # Goal Service
curl http://localhost:8010/health   # Gateway Service
```

---

## Local Development (outside Docker)

For hot-reload development on individual services:

### 1. Start infrastructure only

```bash
make dev
```

This starts databases, RabbitMQ, and Redis only.

### 2. Start individual services

In separate terminals:

```bash
make dev-user-service           # port 8001
make dev-transaction-service    # port 8002
make dev-budget-service         # port 8003
make dev-account-service        # port 8004
make dev-categorization-service # port 8005
make dev-goal-service           # port 8006
make dev-frontend               # port 5173
```

### 3. Install dependencies

```bash
make install-deps
```

---

## First-Time Setup

### Create a user

```bash
curl -X POST http://localhost:8001/api/v1/users/register \
  -H "Content-Type: application/json" \
  -d '{"username": "demo", "email": "demo@example.com", "password": "DemoPass123!"}'
```

### Login

```bash
curl -X POST http://localhost:8001/api/v1/users/login \
  -H "Content-Type: application/json" \
  -d '{"email": "demo@example.com", "password": "DemoPass123!"}'
```

The response includes an `access_token` JWT for authenticating with all other services.

### Verify default account was created

After registration, the account-creation-consumer creates a "Default Account":

```bash
curl http://localhost:8004/api/v1/accounts/ \
  -H "Authorization: Bearer <token>"
```

---

## RabbitMQ Management UI

Open http://localhost:15672 (guest / guest) to inspect:
- Exchanges: `finans_tracker.events` (topic)
- Queues: per-consumer durable queues
- Message rates and consumer status

---

## Troubleshooting

### Services not starting

```bash
docker compose logs <service-name>
```

### Database migrations

Each service runs Alembic migrations on startup. If a service fails with migration errors:

```bash
docker compose exec <service-name> alembic upgrade head
```

### Reset everything

```bash
docker compose down -v   # Removes all data volumes
docker compose up -d     # Fresh start
```

---

## Bank Integration Setup (Optional)

To use live bank connections via Enable Banking:

1. Register at https://enablebanking.com/sign-in/
2. Create an application and download the PEM key
3. Set environment variables:

```bash
ENABLE_BANKING_APP_ID=your-app-id
ENABLE_BANKING_KEY_PATH=./enablebanking-sandbox.pem
ENABLE_BANKING_REDIRECT_URI=http://localhost:8009/api/v1/bank/callback
ENABLE_BANKING_ENVIRONMENT=sandbox
```

These are configured in `docker-compose.yml` for the banking-service.
