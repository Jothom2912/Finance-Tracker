# Installation Guide -- Finance Tracker

## Prerequisites

- **Docker Desktop** installed and running
- **Git** installed
- **8GB RAM** available (minimum 4GB for Elasticsearch)
- **10GB free disk space**

---

## Quick Start

### 1. Clone Repository

```bash
git clone https://github.com/jothom2912/finance-tracker.git
cd finance-tracker
```

### 2. Start All Services

```bash
docker-compose up -d
```

This starts:
- **MySQL** (port 3307)
- **Elasticsearch** (port 9200)
- **Neo4j** (ports 7474, 7687)
- **Backend API** (port 8080)

**Wait 30-60 seconds** for all services to be healthy.

### 3. Verify Services Are Running

```bash
docker-compose ps
docker-compose logs backend
```

### 4. Initialize MySQL Database

Tables are created automatically on first request via SQLAlchemy, or load from a dump:

```bash
docker exec finance-mysql mysql -u root -p123456 finans_tracker < dumps/mysql/finans_tracker.sql
```

If restoring from a backup without the `created_at` column, run the migration:

```bash
# Docker
docker exec finance-backend python -m backend.migrations.mysql.add_created_at_to_transactions

# Local development
uv run python -m backend.migrations.mysql.add_created_at_to_transactions
```

### 4.1. Seed Categories (REQUIRED)

Categories are required before creating transactions or budgets. Works with all three databases:

```bash
# Docker
docker exec finance-backend python -m backend.seed_categories

# Local development
uv run python -m backend.seed_categories
```

### 4.2. Generate Test Data (Optional -- MySQL Only)

```bash
# Docker
docker exec finance-backend python -m backend.generate_dummy_data

# Local development
uv run python -m backend.generate_dummy_data

# Clear and regenerate
uv run python -m backend.generate_dummy_data --clear
```

This creates test users (`johan`, `marie`, `testuser` -- all with password `test123`), accounts, transactions, budgets, goals, and account groups.

For Elasticsearch and Neo4j, seed data via API endpoints or migration scripts.

### 5. Load Elasticsearch Data (Optional)

```bash
docker exec finance-backend python scripts/load_elasticsearch.py
```

### 6. Load Neo4j Data (Optional)

```bash
chmod +x backend/scripts/load_neo4j.sh
cd backend/scripts
./load_neo4j.sh
```

---

## Local Development (Windows)

```powershell
cd backend
uv sync

# Start the API
uv run uvicorn backend.main:app --reload --port 8000
```

- API docs: http://localhost:8000/docs
- Health: http://localhost:8000/health
- GraphQL playground: http://localhost:8000/api/v1/graphql

---

## Verify Installation

### Test Backend Health

```bash
# Docker
curl http://localhost:8080/health

# Local development
curl http://localhost:8000/health
```

Expected response:

```json
{
  "status": "ok",
  "message": "Backend kører!",
  "timestamp": 1234567890.123
}
```

### Test MySQL Connection

```bash
docker exec finance-mysql mysql -u root -p123456 -e "SHOW DATABASES;"
```

### Test Elasticsearch

```bash
curl http://localhost:9200/_cluster/health
```

### Test Neo4j

Open browser: http://localhost:7474 (credentials: `neo4j` / `12345678`)

---

## Switch Between Databases

Edit `.env` file:

```bash
# Use MySQL (default)
ACTIVE_DB=mysql

# Use Elasticsearch
ACTIVE_DB=elasticsearch

# Use Neo4j
ACTIVE_DB=neo4j
```

Restart backend:

```bash
docker-compose restart backend
```

---

## Test API

### 1. Open API Documentation

- **Docker:** http://localhost:8080/docs
- **Local development:** http://localhost:8000/docs

All domain endpoints are versioned under `/api/v1/`.

### 2. Register a User

```bash
# Docker
curl -X POST http://localhost:8080/api/v1/users/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "test123456"
  }'

# Local development
curl -X POST http://localhost:8000/api/v1/users/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "test123456"
  }'
```

### 3. Login

```bash
# Docker
curl -X POST http://localhost:8080/api/v1/users/login \
  -H "Content-Type: application/json" \
  -d '{
    "username_or_email": "testuser",
    "password": "test123456"
  }'

# Local development
curl -X POST http://localhost:8000/api/v1/users/login \
  -H "Content-Type: application/json" \
  -d '{
    "username_or_email": "testuser",
    "password": "test123456"
  }'
```

Save the `access_token` from the response.

### 4. Create a Transaction

```bash
# Docker
curl -X POST http://localhost:8080/api/v1/transactions/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "X-Account-ID: 1" \
  -d '{
    "amount": -100.50,
    "description": "Test transaction",
    "date": "2025-12-09",
    "type": "expense",
    "Category_idCategory": 1
  }'

# Local development
curl -X POST http://localhost:8000/api/v1/transactions/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "X-Account-ID: 1" \
  -d '{
    "amount": -100.50,
    "description": "Test transaction",
    "date": "2025-12-09",
    "type": "expense",
    "Category_idCategory": 1
  }'
```

### 5. Query GraphQL Read Gateway

```bash
curl -X POST http://localhost:8000/api/v1/graphql \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "X-Account-ID: 1" \
  -d '{
    "query": "{ financialOverview(accountId: 1) { totalIncome totalExpenses balance transactionCount } }"
  }'
```

---

## Database Dumps

Test data is available in `dumps/` directory:

- `dumps/mysql/` -- MySQL SQL dump
- `dumps/elasticsearch/` -- JSON exports for each index
- `dumps/neo4j/` -- Neo4j database dump

### Create Dumps

```bash
# Elasticsearch
docker exec finance-backend python scripts/dump_elasticsearch.py

# Neo4j
cd backend/scripts && chmod +x dump_neo4j.sh && ./dump_neo4j.sh

# MySQL
docker exec finance-mysql mysqldump -u root -p123456 finans_tracker > dumps/mysql/finans_tracker.sql
```

---

## Troubleshooting

### MySQL Connection Fails

```bash
docker logs finance-mysql
docker exec finance-mysql mysqladmin ping -h localhost -u root -p123456
```

### Elasticsearch Not Starting

Elasticsearch needs 4GB+ memory. Increase Docker Desktop memory, restart Docker, then:

```bash
docker-compose restart elasticsearch
```

### Neo4j Authentication Error

Default credentials: `neo4j` / `12345678`. To reset:

```bash
docker exec finance-neo4j neo4j-admin set-initial-password newpassword
```

Update `NEO4J_PASSWORD` in `.env` and restart backend.

### Backend Not Starting

```bash
docker logs finance-backend
docker-compose ps
docker-compose build backend
docker-compose up -d backend
```

### Port Already in Use

If ports 3307, 8080, 9200, 7474, or 7687 are in use, stop the conflicting service or change ports in `docker-compose.yml`.

---

## Stop Services

```bash
# Stop (keeps data)
docker-compose down

# Stop and delete all data
docker-compose down -v
```

---

## Default Credentials

| Service | Username | Password |
|---------|----------|----------|
| MySQL | `root` | `123456` |
| Neo4j | `neo4j` | `12345678` |
| Test users | `johan`, `marie`, `testuser` | `test123` |

---

## Useful Commands

```bash
docker-compose logs -f backend      # Follow backend logs
docker exec -it finance-backend bash # Shell into container
docker-compose restart backend       # Restart after changes
docker-compose build backend         # Rebuild after code changes
docker stats                         # Check resource usage
```
