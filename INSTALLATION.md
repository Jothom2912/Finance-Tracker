# Installation Guide — Finance Tracker

## Prerequisites

- **Docker Desktop** installed and running
- **Git** installed
- **Node.js 18+** (for frontend)
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

This starts:

| Service | Port | Description |
|---------|------|-------------|
| **MySQL** | 3307 | Monolith database |
| **PostgreSQL (users)** | 5433 | User-service database |
| **PostgreSQL (transactions)** | 5434 | Transaction-service database |
| **PostgreSQL (goals)** | 5435 | Goal-service database |
| **RabbitMQ** | 5672 / 15672 | Event bus + management UI |
| **Monolith** | 8000 | Accounts, budgets, goals, analytics, bank sync, categorization |
| **User Service** | 8001 | Registration, login, JWT issuing |
| **Transaction Service** | 8002 | Transaction CRUD, CSV import, categories |
| **Goal Service** | 8003 | Goal CRUD and user-validation bridge |
| **Goal Outbox Worker** | — | Publishes goal events from outbox to RabbitMQ |
| **UserSync Consumer** | — | Syncs users from events to MySQL |
| **AccountCreation Consumer** | — | Creates default accounts from events |
| **CategorySync Consumer** | — | Syncs categories from transaction-service to MySQL |

**Wait 30-60 seconds** for all health checks to pass.

### 3. Verify Services Are Running

```bash
docker compose ps
curl http://localhost:8000/health   # Monolith
curl http://localhost:8001/health   # User Service
curl http://localhost:8002/health   # Transaction Service
curl http://localhost:8003/health   # Goal Service
```

### 4. Start Frontend

```bash
cd services/frontend
npm install
npm run dev
```
#fuck yarn!

App: http://localhost:3001

### 5. Seed Database (Optional)

The ten default Categories are seeded automatically in transaction-service via Alembic (migrations 005 + 006) and projected to the monolith MySQL by `category-sync-consumer` at startup — no manual step required. The script below seeds the monolith-owned layer on top (subcategories, merchants, keyword rules) and is still needed before creating transactions or budgets via the monolith:

```bash
# Seed subcategories + merchants (waits for Category projection to land first)
docker exec -it $(docker compose ps -q monolith) python -m backend.scripts.seed_categories

# Generate test data (creates users, accounts, transactions, budgets, goals)
docker exec -it $(docker compose ps -q monolith) python -m backend.generate_dummy_data
```

Test users created by seed: `johan`, `marie`, `testuser` (password: `test123`).

### 6. Connect a Bank (Optional)

To enable live bank transaction sync via PSD2:

1. Register at [Enable Banking](https://enablebanking.com/sign-in/) and create an application
2. Download the sandbox PEM key and place it in the project root as `enablebanking-sandbox.pem`
3. Set environment variables in `.env`:
   - `ENABLE_BANKING_APP_ID` — your application ID
   - `ENABLE_BANKING_KEY_PATH` — path to PEM key (default: `./enablebanking-sandbox.pem`)
   - `ENABLE_BANKING_REDIRECT_URI` — must match what you registered (default: `http://localhost:8000/api/v1/bank/callback`)
   - `ENABLE_BANKING_ENVIRONMENT` — `sandbox` for testing, `production` for live data
4. Start bank connection via API or frontend dashboard
5. Authorize at your bank's login page
6. Sync transactions from the dashboard

---

## User Registration Flow

With the microservices architecture, registering a new user triggers an event-driven flow:

1. **Register** via user-service (port 8001) — creates user in PostgreSQL
2. **user.created event** published to RabbitMQ
3. **UserSyncConsumer** picks up event, inserts user into monolith MySQL
4. **AccountCreationConsumer** picks up event, creates default account in MySQL
5. User can now log in and use the full application

This happens automatically. No manual database setup needed for new users.

---

## Local Development (without Docker)

### Backend (Monolith)

```powershell
cd services/monolith
uv sync --dev
uv run uvicorn backend.main:app --reload --port 8000
```

You need MySQL running locally (or via Docker) with `DATABASE_URL` set in `.env`.

### User Service

```powershell
cd services/user-service
uv sync --dev
uv run uvicorn app.main:app --reload --port 8001
```

Needs PostgreSQL on port 5433 and RabbitMQ on port 5672.

### Transaction Service

```powershell
cd services/transaction-service
uv sync --dev
uv run uvicorn app.main:app --reload --port 8002
```

Needs PostgreSQL on port 5434 and RabbitMQ on port 5672.

### Goal Service

```powershell
cd services/goal-service
uv sync --dev
uv run uvicorn app.main:app --reload --port 8003
```

Needs PostgreSQL on port 5435, user-service on port 8001, and RabbitMQ on port 5672.

### Consumers

```powershell
# In separate terminals (from services/monolith/)
cd services/monolith
uv run python -m backend.consumers.worker --consumer user-sync
uv run python -m backend.consumers.worker --consumer account-creation
uv run python -m backend.consumers.worker --consumer category-sync
```

### Frontend

```powershell
cd services/frontend
npm install
npm run dev
```

- API docs: http://localhost:8000/docs
- Health: http://localhost:8000/health, http://localhost:8001/health, http://localhost:8002/health, http://localhost:8003/health
- GraphQL playground: http://localhost:8000/api/v1/graphql
- RabbitMQ Management: http://localhost:15672 (guest/guest)

---

## Test the API

### 1. Register a User (via User Service)

```bash
curl -X POST http://localhost:8001/api/v1/users/register \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "email": "test@example.com", "password": "SecurePass123!"}'
```

### 2. Login (via User Service)

```bash
curl -X POST http://localhost:8001/api/v1/users/login \
  -d "username=test@example.com&password=SecurePass123!"
```

Save the `access_token` from the response. This token works on all services.

### 3. Create a Transaction (via Transaction Service)

```bash
curl -X POST http://localhost:8002/api/v1/transactions/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "account_id": 1,
    "account_name": "Default Account",
    "amount": "100.50",
    "transaction_type": "expense",
    "description": "Groceries",
    "date": "2026-03-11"
  }'
```

### 4. Create a Transaction (via Monolith)

```bash
curl -X POST http://localhost:8000/api/v1/transactions/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "X-Account-ID: 1" \
  -d '{"amount": -100.50, "description": "Groceries", "date": "2026-03-11", "type": "expense", "Category_idCategory": 1}'
```

### 5. Query GraphQL Read Gateway

```bash
curl -X POST http://localhost:8000/api/v1/graphql \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "X-Account-ID: 1" \
  -d '{"query": "{ financialOverview(accountId: 1) { totalIncome totalExpenses balance transactionCount } }"}'
```

---

## Running Tests

```bash
# All tests via root Makefile
make test

# Monolith tests (335 tests)
cd services/monolith && uv run pytest tests/ -v

# Frontend tests (96 tests)
cd services/frontend && npx vitest run

# User service tests (40 tests)
cd services/user-service && uv run pytest tests/ -v

# Transaction service tests (104 tests)
cd services/transaction-service && uv run pytest tests/ -v

# E2E tests (requires docker compose up)
uv run pytest tests/e2e/ -v -m e2e
```

---

## Troubleshooting

### Service Not Starting

```bash
docker compose logs <service-name>
docker compose ps
```

### MySQL Connection Fails

The MySQL password in docker-compose is `root`. If you previously used a different password, the old volume remembers it:

```bash
# Reset volumes (WARNING: deletes all data)
docker compose down -v
docker compose up -d
```

### Consumer Not Processing Events

Check RabbitMQ Management UI at http://localhost:15672 (guest/guest). Look for:
- Queues `monolith.user_sync` and `monolith.account_creation`
- Dead-letter queues `*.dlq` for failed messages
- Consumer logs: `docker compose logs user-sync-consumer` or `docker compose logs account-creation-consumer`

### JWT Token Invalid Across Services

All services must share the same JWT secret. In docker-compose, the monolith uses `SECRET_KEY` and microservices use `JWT_SECRET` — both are set to `dev-secret-key-change-in-production`.

### Port Already in Use

| Port | Service | Alternative |
|------|---------|-------------|
| 3307 | MySQL | Change in docker-compose |
| 5433 | PostgreSQL (users) | Change in docker-compose |
| 5434 | PostgreSQL (transactions) | Change in docker-compose |
| 5435 | PostgreSQL (goals) | Change in docker-compose |
| 5672 | RabbitMQ | Change in docker-compose |
| 8000 | Monolith | Change in docker-compose |
| 8001 | User Service | Change in docker-compose |
| 8002 | Transaction Service | Change in docker-compose |
| 8003 | Goal Service | Change in docker-compose |

---

## Stop Services

```bash
# Stop (keeps data in volumes)
docker compose down

# Stop and delete all data (fresh start)
docker compose down -v
```

---

## Default Credentials (Development)

| Service | Username | Password |
|---------|----------|----------|
| MySQL | `root` | `root` |
| RabbitMQ | `guest` | `guest` |
| RabbitMQ Management UI | `guest` | `guest` |
| Seeded test users | `johan`, `marie`, `testuser` | `test123` |
