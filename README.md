# 💰 Personal Finance Tracker - Multi-Database Implementation

A modern personal finance tracking application demonstrating **Clean Architecture** and **Repository Pattern** by implementing the same business logic across three different databases: **MySQL**, **Elasticsearch**, and **Neo4j**.

## 🎯 Project Overview

This project showcases:
- **Clean Architecture** with clear separation of concerns
- **Repository Pattern** for database abstraction
- **Multi-database support** - Switch between MySQL, Elasticsearch, and Neo4j seamlessly
- **RESTful API** built with FastAPI
- **JWT Authentication** with secure password hashing
- **Modern Frontend** built with React

### Key Features

- 📊 **Transaction Management** - Track income and expenses
- 💰 **Budget Planning** - Set and monitor budgets
- 🎯 **Financial Goals** - Set savings goals and track progress
- 📈 **Dashboard Analytics** - Financial overview and insights
- 🔍 **Advanced Search** - Full-text search with Elasticsearch
- 🕸️ **Graph Queries** - Relationship analysis with Neo4j
- 📁 **CSV Import** - Bulk import transactions from CSV files
- 🏷️ **Auto-Categorization** - Automatic transaction categorization

---

## 🚀 Quick Start

### Prerequisites

- Docker Desktop installed and running
- Git installed
- 8GB RAM available (minimum 4GB for Elasticsearch)

### Installation

See [INSTALLATION.md](INSTALLATION.md) for detailed setup instructions.

```bash
# Clone repository
git clone https://github.com/yourusername/finance-tracker.git
cd finance-tracker

# Start all services
docker-compose up -d

# Wait for services to be healthy (30-60 seconds)
docker-compose ps

# Access the application
# - API: http://localhost:8080/docs
# - Neo4j Browser: http://localhost:7474
```

---

## 📁 Project Structure

```
finance-tracker/
├── backend/
│   ├── database/          # Database connections (MySQL, ES, Neo4j)
│   ├── models/            # Database models
│   │   ├── mysql/         # SQLAlchemy models
│   │   ├── elasticsearch/  # ES mappings
│   │   └── neo4j/         # Cypher templates
│   ├── repositories/      # 🎯 Repository Pattern
│   │   ├── base.py        # Abstract interfaces
│   │   ├── mysql/         # MySQL implementations
│   │   ├── elasticsearch/  # Elasticsearch implementations
│   │   └── neo4j/         # Neo4j implementations
│   ├── services/          # Business logic
│   ├── routes/            # FastAPI endpoints
│   ├── shared/            # Shared schemas and exceptions
│   ├── migrations/        # Database migrations
│   └── scripts/           # Dump/load scripts
├── frontend/              # React frontend
├── dumps/                 # Database dumps
│   ├── mysql/
│   ├── elasticsearch/
│   └── neo4j/
├── docker-compose.yml     # Docker services
├── Dockerfile             # Backend container
├── INSTALLATION.md        # Setup guide
└── README.md             # This file
```

---

## 🔄 Switch Between Databases

The application supports three databases. Switch by changing `ACTIVE_DB` in `.env` or environment variables:

```bash
# Use MySQL (default - ACID transactions, relations)
ACTIVE_DB=mysql

# Use Elasticsearch (full-text search, analytics)
ACTIVE_DB=elasticsearch

# Use Neo4j (graph queries, relationships)
ACTIVE_DB=neo4j
```

**No code changes required!** The Repository Pattern handles the switch automatically.

---

## 🗄️ Database Comparison

| Feature | MySQL | Elasticsearch | Neo4j |
|---------|-------|---------------|-------|
| **Primary Use** | CRUD operations | Search & Analytics | Graph queries |
| **Strengths** | ACID, Relations | Full-text search | Relationship traversal |
| **Best For** | Primary data store | Search, aggregations | Network analysis |
| **Query Language** | SQL | Query DSL | Cypher |

See [backend/DATABASE_COMPARISON.md](backend/DATABASE_COMPARISON.md) for detailed comparison.

---

## 📊 API Endpoints

### Authentication
- `POST /users/` - Register new user
- `POST /users/login` - Login and get JWT token

### Transactions
- `GET /transactions/` - List transactions
- `POST /transactions/` - Create transaction
- `PUT /transactions/{id}` - Update transaction
- `DELETE /transactions/{id}` - Delete transaction
- `POST /transactions/upload-csv/` - Bulk import from CSV

### Accounts
- `GET /accounts/` - List accounts
- `POST /accounts/` - Create account
- `PUT /accounts/{id}` - Update account
- `DELETE /accounts/{id}` - Delete account

### Budgets & Goals
- `GET /budgets/` - List budgets
- `POST /budgets/` - Create budget
- `GET /goals/` - List goals
- `POST /goals/` - Create goal

### Dashboard
- `GET /dashboard/overview/` - Financial overview
- `GET /dashboard/expenses-by-month/` - Monthly expenses

**Full API Documentation:**
- Docker: http://localhost:8080/docs
- Local development: http://localhost:8000/docs

---

## 🧪 Testing

### Test Repositories

```bash
cd backend
python test_repositories.py
```

### Run Tests

```bash
pytest backend/tests/
```

---

## 📦 Database Dumps

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

## 🏗️ Architecture

### Repository Pattern

The application uses the Repository Pattern to abstract database operations:

```python
# ✅ FastAPI Routes (with session management)
from fastapi import Depends
from sqlalchemy.orm import Session
from backend.database.mysql import get_db
from backend.repositories import get_transaction_repository

@router.get("/")
def get_transactions(db: Session = Depends(get_db)):
    repo = get_transaction_repository(db)  # Pass session for MySQL
    return repo.get_all(account_id=1)

# ✅ Scripts (manual session management)
from backend.database.mysql import SessionLocal
from backend.repositories import get_transaction_repository
from backend.config import ACTIVE_DB

db = SessionLocal() if ACTIVE_DB == "mysql" else None
try:
    repo = get_transaction_repository(db) if ACTIVE_DB == "mysql" else get_transaction_repository()
    transactions = repo.get_all(account_id=1)
finally:
    if db:
        db.close()
```

**Benefits:**
- ✅ Easy database switching
- ✅ Testable (can mock repositories)
- ✅ Clean separation of concerns
- ✅ Type-safe interfaces
- ✅ Proper session management (MySQL requires session, ES/Neo4j don't)

### Clean Architecture Layers

```
Routes (API) → Services (Business Logic) → Repositories (Data Access) → Database
```

See [backend/docs/PROJECT_OVERVIEW.md](backend/docs/PROJECT_OVERVIEW.md) for detailed architecture documentation.

---

## 🔐 Security

- **JWT Authentication** - Secure token-based auth
- **Password Hashing** - bcrypt with 12 rounds
- **Protected Routes** - Authentication required for sensitive endpoints
- **Account Isolation** - Users can only access their own data
- **Input Validation** - Pydantic schemas validate all inputs

---

## 📚 Documentation

- [Installation Guide](INSTALLATION.md) - Setup instructions
- [Project Overview](backend/docs/PROJECT_OVERVIEW.md) - Architecture and flow
- [Project Status](backend/docs/PROJECT_STATUS.md) - What's implemented
- [Backend Readiness](backend/docs/BACKEND_READINESS.md) - Current status
- [Repository Pattern](backend/repositories/README.md) - Repository guide
- [Database Comparison](backend/DATABASE_COMPARISON.md) - Database details

---

## 🛠️ Development

### Local Development (Without Docker)

```bash
# Backend
cd backend
pip install -r requirements.txt
python -m uvicorn backend.main:app --reload --port 8000

# Frontend
cd frontend/finans-tracker-frontend
npm install
npm start
```

**Note:** When running locally, API is available at http://localhost:8000/docs (not 8080)

### Environment Variables

Create `.env` file:

```bash
# Database
ACTIVE_DB=mysql
DATABASE_URL=mysql+pymysql://user:password@localhost:3307/finans_tracker

# Elasticsearch
ELASTICSEARCH_HOST=http://localhost:9200

# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=12345678

# JWT Secret
SECRET_KEY=your-secret-key-here
```

---

## 🐛 Troubleshooting

See [INSTALLATION.md](INSTALLATION.md#-troubleshooting) for common issues and solutions.

---

## 📝 License

MIT License - See LICENSE file for details

---

## 🙏 Acknowledgments

- **FastAPI** - Modern Python web framework
- **SQLAlchemy** - Python SQL toolkit
- **Elasticsearch** - Search and analytics engine
- **Neo4j** - Graph database
- **React** - Frontend framework

---

## 🚧 Roadmap

- [ ] Unit and integration tests
- [ ] Rate limiting and security hardening
- [ ] Database migrations with Alembic
- [ ] Export functionality (PDF, Excel)
- [ ] Recurring transactions
- [ ] Notifications and alerts
- [ ] GraphQL endpoint activation

---

## 📧 Contact

For questions or issues, please open an issue on GitHub.

---

**Built with ❤️ using Clean Architecture and Repository Pattern**

