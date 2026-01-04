# 📦 Installation Guide - Finance Tracker

## Prerequisites

- **Docker Desktop** installed and running
- **Git** installed
- **8GB RAM** available (minimum 4GB for Elasticsearch)
- **10GB free disk space**

---

## 🚀 Quick Start

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
# Check all containers
docker-compose ps

# Check logs
docker-compose logs backend
```

### 4. Initialize MySQL Database

The database tables will be created automatically on first request, or you can run:

```bash
# Option 1: Let SQLAlchemy create tables automatically (recommended)
# Just make a request to any endpoint

# Option 2: Load from dump (if you have one)
docker exec finance-mysql mysql -u root -p123456 finans_tracker < dumps/mysql/finans_tracker.sql
```

### 4.1. Seed Categories (REQUIRED)

**⚠️ IMPORTANT:** You **must** seed categories before using the application. Categories are required for:
- Creating transactions
- Creating budgets
- Categorizing transactions

**Works with all 3 databases (MySQL, Elasticsearch, Neo4j):**

```bash
# ✅ Docker
docker exec finance-backend python -m backend.seed_categories

# ✅ Local development
python -m backend.seed_categories
```

This will create all necessary categories (expense and income) based on the categorization rules. You should see output like:
```
Tilføjet X nye kategorier til databasen.
```

### 4.2. Generate Test Data (Optional - MySQL Only)

**⚠️ NOTE:** `generate_dummy_data.py` only works with MySQL. For Elasticsearch and Neo4j, seed data via API or use migration scripts.

If you want test data (users, accounts, transactions, budgets, etc.):

```bash
# ✅ Docker (MySQL only)
docker exec finance-backend python -m backend.generate_dummy_data

# ✅ Local development (MySQL only)
python -m backend.generate_dummy_data

# Regenerate / clear dummy data
python -m backend.generate_dummy_data --clear
```

This creates:
- **3 test users** (johan, marie, testuser + 7 more - all with password: `test123`)
- Test accounts
- Test categories (if not already seeded)
- Test transactions
- Test PlannedTransactions
- Test budgets
- Test goals
- Account groups

**Note:** 
- If you already seeded categories in step 4.1, the script will use existing categories instead of creating duplicates.
- For Elasticsearch and Neo4j, you'll need to seed data separately via API endpoints or migration scripts.

### 5. Load Elasticsearch Data (Optional)

If you have Elasticsearch dumps:

```bash
docker exec finance-backend python scripts/load_elasticsearch.py
```

### 6. Load Neo4j Data (Optional)

If you have Neo4j dumps:

```bash
# Make script executable
chmod +x backend/scripts/load_neo4j.sh

# Run load script
cd backend/scripts
./load_neo4j.sh
```

---

## ✅ Verify Installation

### Test Backend Health

**Docker:**
```bash
curl http://localhost:8080/health
```

**Local development:**
```bash
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

**Default credentials:**
- Username: `root`
- Password: `123456`

### Test Elasticsearch

```bash
curl http://localhost:9200/_cluster/health
```

Expected response:
```json
{
  "cluster_name": "docker-cluster",
  "status": "green",
  ...
}
```

### Test Neo4j

Open browser: **http://localhost:7474**

**Default credentials:**
- Username: `neo4j`
- Password: `12345678`

---

## 🔄 Switch Between Databases

Edit `.env` file (or set environment variable):

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

## 🧪 Test API

### 1. Open API Documentation

**Docker:** Open browser: **http://localhost:8080/docs**  
**Local development:** Open browser: **http://localhost:8000/docs**

This shows the interactive Swagger UI with all endpoints.

### 2. Register a User

**Docker:**
```bash
curl -X POST http://localhost:8080/users/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "test123456"
  }'
```

**Local development:**
```bash
curl -X POST http://localhost:8000/users/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "test123456"
  }'
```

### 3. Login

**Docker:**
```bash
curl -X POST http://localhost:8080/users/login \
  -H "Content-Type: application/json" \
  -d '{
    "username_or_email": "testuser",
    "password": "test123456"
  }'
```

**Local development:**
```bash
curl -X POST http://localhost:8000/users/login \
  -H "Content-Type: application/json" \
  -d '{
    "username_or_email": "testuser",
    "password": "test123456"
  }'
```

Save the `access_token` from the response.

### 4. Create a Transaction

**Docker:**
```bash
curl -X POST http://localhost:8080/transactions/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "X-Account-ID: 1" \
  -d '{
    "amount": -100.50,
    "description": "Test transaction",
    "date": "2024-12-09",
    "type": "expense",
    "Category_idCategory": 1
  }'
```

**Local development:**
```bash
curl -X POST http://localhost:8000/transactions/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "X-Account-ID: 1" \
  -d '{
    "amount": -100.50,
    "description": "Test transaction",
    "date": "2024-12-09",
    "type": "expense",
    "Category_idCategory": 1
  }'
```

---

## 📊 Database Dumps

Test data is available in `dumps/` directory:

- `dumps/mysql/` - MySQL SQL dump
- `dumps/elasticsearch/` - JSON exports for each index
- `dumps/neo4j/` - Neo4j database dump

### Create Dumps

**Elasticsearch:**
```bash
docker exec finance-backend python scripts/dump_elasticsearch.py
```

**Neo4j:**
```bash
cd backend/scripts
chmod +x dump_neo4j.sh
./dump_neo4j.sh
```

**MySQL:**
```bash
docker exec finance-mysql mysqldump -u root -p123456 finans_tracker > dumps/mysql/finans_tracker.sql
```

---

## 🔧 Troubleshooting

### MySQL Connection Fails

```bash
# Check MySQL logs
docker logs finance-mysql

# Check if MySQL is healthy
docker exec finance-mysql mysqladmin ping -h localhost -u root -p123456
```

### Elasticsearch Not Starting

**Problem:** Elasticsearch needs more memory

**Solution:**
1. Increase Docker Desktop memory to **4GB+**
2. Restart Docker Desktop
3. Restart containers: `docker-compose restart elasticsearch`

### Neo4j Authentication Error

**Default credentials:**
- Username: `neo4j`
- Password: `12345678`

**Reset password:**
```bash
docker exec finance-neo4j neo4j-admin set-initial-password newpassword
```

**Note:** After resetting password, update `NEO4J_PASSWORD` in `.env` file and restart backend.

### Backend Not Starting

```bash
# Check backend logs
docker logs finance-backend

# Check if all dependencies are healthy
docker-compose ps

# Rebuild backend
docker-compose build backend
docker-compose up -d backend
```

### Port Already in Use

If ports 3307, 8080, 9200, 7474, or 7687 are already in use:

1. Stop the service using the port
2. Or change ports in `docker-compose.yml`:
   ```yaml
   ports:
     - "3308:3306"  # Changed from 3307
   ```

---

## 🛑 Stop All Services

```bash
docker-compose down
```

This stops all containers but **keeps the data**.

---

## 🗑️ Clean Everything (Including Data)

**⚠️ WARNING: This deletes all data!**

```bash
docker-compose down -v
```

This removes:
- All containers
- All volumes (database data)
- All networks

---

## 📁 Project Structure

```
finance-tracker/
├── backend/
│   ├── scripts/
│   │   ├── dump_elasticsearch.py
│   │   ├── load_elasticsearch.py
│   │   ├── dump_neo4j.sh
│   │   └── load_neo4j.sh
│   ├── dumps/          # Created automatically
│   └── ...
├── dumps/
│   ├── mysql/
│   ├── elasticsearch/
│   └── neo4j/
├── docker-compose.yml
├── Dockerfile
└── INSTALLATION.md
```

---

## 🔗 Useful Commands

```bash
# View logs
docker-compose logs -f backend

# Execute command in container
docker exec -it finance-backend bash

# Restart a service
docker-compose restart backend

# Rebuild after code changes
docker-compose build backend
docker-compose up -d backend

# Check resource usage
docker stats
```

---

## 📚 Next Steps

1. **Explore API:** 
   - Docker: Visit http://localhost:8080/docs
   - Local: Visit http://localhost:8000/docs
2. **Load Test Data:** Use dump scripts to load sample data
3. **Switch Databases:** Try different `ACTIVE_DB` values
4. **Read Documentation:** Check `backend/docs/` folder for architecture details

## 🔐 Default Credentials

- **MySQL:** `root` / `123456`
- **Neo4j:** `neo4j` / `12345678`
- **Test Users:** `johan`, `marie`, `testuser` / `test123`

---

## 🆘 Need Help?

- Check logs: `docker-compose logs`
- Review documentation in `backend/docs/`
- Check GitHub issues
- Verify all prerequisites are installed

---

**Happy coding! 🚀**

