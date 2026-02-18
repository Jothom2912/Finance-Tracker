# Personal Finance Tracker - Multi-Database Implementation

A modern personal finance tracking application demonstrating **Clean Architecture** and **Repository Pattern** by implementing the same business logic across three different databases: **MySQL**, **Elasticsearch**, and **Neo4j**.

## Table of Contents

- [Project Overview](#project-overview)
- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Switch Between Databases](#switch-between-databases)
- [Database Comparison](#database-comparison)
- [API Endpoints](#api-endpoints)
- [Testing](#testing)
- [Database Dumps](#database-dumps)
- [Security](#security)
- [Development](#development)
- [Troubleshooting](#troubleshooting)
- [Documentation](#documentation)
- [License](#license)

---

## Project Overview

This project showcases:
- **Clean Architecture** with clear separation of concerns
- **Repository Pattern** for database abstraction
- **Multi-database support** - Switch between MySQL, Elasticsearch, and Neo4j seamlessly
- **RESTful API** built with FastAPI
- **JWT Authentication** with secure password hashing
- **Modern Frontend** built with React

### Key Features

- **Transaction Management** - Track income and expenses with CSV import
- **Budget Planning** - Set budgets per category with summary and aggregation
- **Financial Goals** - Set savings goals and track progress
- **Dashboard Analytics** - Financial overview, monthly breakdowns, category insights
- **Account Groups** - Group accounts for household or shared budgets
- **Planned Transactions** - Schedule future recurring transactions
- **Multi-Database** - Switch between MySQL, Elasticsearch, and Neo4j
- **Auto-Categorization** - Automatic transaction categorization from CSV

---

## Quick Start

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

## Project Structure

```
finance-tracker/
├── backend/
│   ├── main.py              # FastAPI app entry point
│   ├── config.py            # Centralized environment config
│   ├── auth.py              # JWT auth + password hashing (bcrypt)
│   ├── dependencies.py      # FastAPI DI wiring (service factories)
│   │
│   ├── database/            # Database connections
│   │   ├── mysql.py         # SQLAlchemy engine + session
│   │   ├── elasticsearch.py # ES client
│   │   └── neo4j.py         # Neo4j driver
│   │
│   ├── models/mysql/        # SQLAlchemy ORM models
│   │   ├── user.py          # User model
│   │   ├── account.py       # Account model
│   │   ├── transaction.py   # Transaction model
│   │   ├── category.py      # Category model
│   │   ├── budget.py        # Budget model
│   │   ├── goal.py          # Goal model
│   │   ├── planned_transactions.py
│   │   ├── account_groups.py
│   │   └── common.py        # Base, enums, association tables
│   │
│   ├── repositories/        # Repository Pattern
│   │   ├── base.py          # Abstract interfaces (ABC)
│   │   ├── __init__.py      # Repository factory functions
│   │   ├── mysql/           # MySQL implementations (8 repos)
│   │   ├── elasticsearch/   # Elasticsearch implementations
│   │   └── neo4j/           # Neo4j implementations
│   │
│   ├── services/            # Business logic (class-based + DI)
│   │   ├── transaction_service.py  # Transactions + planned transactions
│   │   ├── account_service.py      # Accounts + account groups
│   │   ├── budget_service.py       # Budgets + summary calculations
│   │   ├── category_service.py     # Category CRUD + duplicate check
│   │   ├── goal_service.py         # Savings goals
│   │   ├── dashboard_service.py    # Financial analytics
│   │   └── user_service.py         # Registration, login, JWT
│   │
│   ├── routes/              # FastAPI endpoint routers
│   ├── shared/schemas/      # Pydantic validation schemas
│   ├── shared/exceptions/   # Custom business exceptions
│   │
│   └── tests/               # Test suite (321 tests)
│       ├── unittests/
│       │   ├── services/    # Service unit tests (7 files, 150 tests)
│       │   ├── test_*.py    # Schema BVA tests (12 files, 143 tests)
│       │   └── ...
│       └── integration/
│           ├── conftest.py  # Shared fixtures, Factory, auth helpers
│           ├── test_transaction_flow.py
│           ├── test_budget_flow.py
│           ├── test_account_flow.py
│           └── test_goal_flow.py
│
├── frontend/                # React frontend
├── dumps/                   # Database dumps (MySQL, ES, Neo4j)
├── docker-compose.yml       # Docker services
├── Dockerfile               # Backend container
├── INSTALLATION.md          # Setup guide
└── README.md                # This file
```

---

## Switch Between Databases

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

## Database Comparison

| Feature | MySQL | Elasticsearch | Neo4j |
|---------|-------|---------------|-------|
| **Primary Use** | CRUD operations | Search & Analytics | Graph queries |
| **Strengths** | ACID, Relations | Full-text search | Relationship traversal |
| **Best For** | Primary data store | Search, aggregations | Network analysis |
| **Query Language** | SQL | Query DSL | Cypher |

See [backend/DATABASE_COMPARISON.md](backend/DATABASE_COMPARISON.md) for detailed comparison.

---

## API Endpoints

### Authentication

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| `POST` | `/users/` | Register new user | No |
| `POST` | `/users/login` | Login and get JWT token | No |
| `GET` | `/users/{user_id}` | Get user details | Yes |

### Transactions

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| `GET` | `/transactions/` | List transactions (with filters) | Yes |
| `POST` | `/transactions/` | Create transaction | Yes |
| `GET` | `/transactions/{id}` | Get transaction by ID | Yes |
| `PUT` | `/transactions/{id}` | Update transaction | Yes |
| `DELETE` | `/transactions/{id}` | Delete transaction | Yes |
| `POST` | `/transactions/upload-csv/` | Bulk import from CSV | Yes |

**Query Parameters:**
- `start_date` - Filter by start date
- `end_date` - Filter by end date
- `type` - Filter by type (income/expense)
- `category_id` - Filter by category

### Accounts

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| `GET` | `/accounts/` | List user's accounts | Yes |
| `POST` | `/accounts/` | Create account | Yes |
| `GET` | `/accounts/{id}` | Get account by ID | Yes |
| `PUT` | `/accounts/{id}` | Update account | Yes |
| `DELETE` | `/accounts/{id}` | Delete account | Yes |

### Categories

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| `GET` | `/categories/` | List all categories | No |
| `POST` | `/categories/` | Create category | Yes |
| `GET` | `/categories/{id}` | Get category by ID | No |

### Budgets

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| `GET` | `/budgets/` | List budgets (with filters) | Yes |
| `POST` | `/budgets/` | Create budget | Yes |
| `GET` | `/budgets/{id}` | Get budget by ID | Yes |
| `PUT` | `/budgets/{id}` | Update budget | Yes |
| `DELETE` | `/budgets/{id}` | Delete budget | Yes |
| `GET` | `/budgets/{id}/summary` | Get budget summary | Yes |

**Query Parameters:**
- `month` - Filter by month (MM format)
- `year` - Filter by year (YYYY format)

### Goals

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| `GET` | `/goals/` | List goals | Yes |
| `POST` | `/goals/` | Create goal | Yes |
| `GET` | `/goals/{id}` | Get goal by ID | Yes |
| `PUT` | `/goals/{id}` | Update goal | Yes |
| `DELETE` | `/goals/{id}` | Delete goal | Yes |

### Dashboard

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| `GET` | `/dashboard/overview/` | Financial overview statistics | Yes |
| `GET` | `/dashboard/expenses-by-month/` | Monthly expenses breakdown | Yes |

### Account Groups

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| `GET` | `/account-groups/` | List account groups | No |
| `POST` | `/account-groups/` | Create account group | No |
| `GET` | `/account-groups/{id}` | Get account group by ID | No |
| `PUT` | `/account-groups/{id}` | Update account group | No |

### Planned Transactions

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| `GET` | `/planned-transactions/` | List planned transactions | Yes |
| `POST` | `/planned-transactions/` | Create planned transaction | Yes |
| `GET` | `/planned-transactions/{id}` | Get planned transaction | Yes |
| `PUT` | `/planned-transactions/{id}` | Update planned transaction | Yes |

**Full API Documentation:**
- **Docker:** http://localhost:8080/docs
- **Local development:** http://localhost:8000/docs

**Authentication:**
- Include JWT token in `Authorization` header: `Bearer <token>`
- Include account context in `X-Account-ID` header (optional, defaults to user's first account)

---

## Testing

The project has **321 tests** organized following the Testing Pyramid:

```
     +----------+
     |   E2E    |   (future - Playwright)
     +----------+
     | Integr.  |   30 tests - Full HTTP flow
     +----------+
     |   Unit   |   291 tests - Business logic + schema validation
     +----------+
```

### Test Structure

```
backend/tests/
├── unittests/
│   ├── services/                    # Service layer unit tests (150 tests)
│   │   ├── test_transaction_service.py   # 53 tests
│   │   ├── test_account_service.py       # 23 tests
│   │   ├── test_budget_service.py        # 17 tests
│   │   ├── test_category_service.py      # 14 tests
│   │   ├── test_goal_service.py          # 13 tests
│   │   ├── test_dashboard_service.py     # 14 tests
│   │   └── test_user_service.py          # 16 tests
│   │
│   ├── test_transaction.py          # Schema BVA validation tests
│   ├── test_budget.py
│   ├── test_category.py
│   ├── test_goal.py
│   ├── test_user.py
│   └── ...                          # 141 schema/BVA tests total
│
└── integration/                     # Full HTTP stack tests (30 tests)
    ├── conftest.py                  # Shared fixtures, Factory, auth helpers
    ├── test_transaction_flow.py     # Transaction creation + CSV import
    ├── test_budget_flow.py          # Budget CRUD + summary with aggregation
    ├── test_account_flow.py         # Account CRUD + auth checks
    └── test_goal_flow.py            # Goal CRUD + progress tracking
```

### Running Tests

```bash
# Run all tests (321 tests)
pytest backend/tests/ -v

# Run only unit tests
pytest backend/tests/unittests/ -v

# Run only service unit tests
pytest backend/tests/unittests/services/ -v

# Run only integration tests
pytest backend/tests/integration/ -v

# Run with coverage
pytest backend/tests/ --cov=backend --cov-report=html
```

### Test Patterns

**Unit tests** use mocked repositories (no database):

```python
class TestTransactionService:
    def setup_method(self):
        self.mock_transaction_repo = Mock(spec=ITransactionRepository)
        self.mock_category_repo = Mock(spec=ICategoryRepository)
        self.service = TransactionService(
            transaction_repo=self.mock_transaction_repo,
            category_repo=self.mock_category_repo,
        )

    def test_create_transaction_validates_category(self):
        self.mock_category_repo.get_by_id.return_value = None
        with pytest.raises(ValueError):
            self.service.create_transaction(transaction_data)
```

**Integration tests** use in-memory SQLite with real repositories:

```python
def test_create_account_returns_201(self, test_client, auth_headers, mock_repositories):
    response = test_client.post(
        "/accounts/",
        json={"name": "Opsparingskonto", "saldo": 25000.0},
        headers=auth_headers,
    )
    assert response.status_code == 201
    assert response.json()["name"] == "Opsparingskonto"
```

---

## Database Dumps

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

## Architecture

### System Overview

The application follows **Clean Architecture** principles with class-based services, constructor-injected dependencies, and the Repository Pattern. This enables seamless switching between MySQL, Elasticsearch, and Neo4j databases without changing business logic.

### Architecture Diagram

```mermaid
graph TB
    subgraph "Frontend Layer"
        FE[React Frontend]
    end
    
    subgraph "Backend Layer - FastAPI"
        subgraph "Presentation Layer"
            ROUTES[API Routes]
            AUTH[JWT Authentication]
        end
        
        subgraph "Dependency Injection"
            DI[dependencies.py]
            FACTORY[Repository Factory]
        end
        
        subgraph "Application Layer"
            TS[TransactionService]
            AS[AccountService]
            BS[BudgetService]
            CS[CategoryService]
            GS[GoalService]
            DS[DashboardService]
            US[UserService]
        end
        
        subgraph "Domain Layer"
            INTERFACES["Repository Interfaces (ABC)"]
        end
        
        subgraph "Infrastructure Layer"
            MYSQL_REPO[MySQL Repositories]
            ES_REPO[ES Repositories]
            NEO4J_REPO[Neo4j Repositories]
        end
    end
    
    subgraph "Database Layer"
        MYSQL[(MySQL)]
        ES[(Elasticsearch)]
        NEO4J[(Neo4j)]
    end
    
    FE --> ROUTES
    ROUTES --> AUTH
    ROUTES --> DI
    DI --> FACTORY
    FACTORY --> MYSQL_REPO
    FACTORY --> ES_REPO
    FACTORY --> NEO4J_REPO
    DI --> TS
    DI --> AS
    DI --> BS
    DI --> CS
    DI --> GS
    DI --> DS
    DI --> US
    TS --> INTERFACES
    AS --> INTERFACES
    BS --> INTERFACES
    CS --> INTERFACES
    GS --> INTERFACES
    DS --> INTERFACES
    US --> INTERFACES
    MYSQL_REPO --> MYSQL
    ES_REPO --> ES
    NEO4J_REPO --> NEO4J
```

### Clean Architecture Layers

```
+---------------------------------------------------+
|  Presentation Layer (routes/)                     |  HTTP endpoints, request/response
+---------------------------------------------------+
|  Dependency Injection (dependencies.py)           |  Service factory + repo wiring
+---------------------------------------------------+
|  Application Layer (services/)                    |  Business logic (class-based)
+---------------------------------------------------+
|  Domain Layer (repositories/base.py)              |  Abstract interfaces (ABC)
+---------------------------------------------------+
|  Infrastructure Layer (repositories/mysql|es|neo) |  Database implementations
+---------------------------------------------------+
```

**Key design decisions:**

1. **Services are classes** that receive repository interfaces via constructor injection
2. **`dependencies.py`** wires services with concrete repos using FastAPI `Depends()`
3. **Routes never access repositories directly** - they only interact with services
4. **No `db: Session` parameter in services** - the session is encapsulated in repos

### Dependency Injection Flow

```mermaid
sequenceDiagram
    participant Route as API Route
    participant DI as dependencies.py
    participant Factory as Repo Factory
    participant Service as TransactionService
    participant Repo as ITransactionRepository

    Route->>DI: Depends(get_transaction_service)
    DI->>Factory: get_transaction_repository(db)
    Factory-->>DI: MySQLTransactionRepository(db)
    DI->>Service: TransactionService(transaction_repo, category_repo)
    Route->>Service: service.create_transaction(data)
    Service->>Repo: self._transaction_repo.create(...)
    Repo-->>Service: Created transaction dict
    Service-->>Route: Result
```

### Service DI Pattern

All seven services follow the same pattern:

```python
from backend.repositories.base import ITransactionRepository, ICategoryRepository

class TransactionService:
    """Business logic for transactions. Receives repositories via constructor."""
    
    def __init__(
        self,
        transaction_repo: ITransactionRepository,
        category_repo: ICategoryRepository,
        planned_transaction_repo: IPlannedTransactionRepository = None,
    ):
        self._transaction_repo = transaction_repo
        self._category_repo = category_repo
        self._planned_transaction_repo = planned_transaction_repo

    def create_transaction(self, transaction: TransactionCreate):
        # Validate category exists
        category = self._category_repo.get_by_id(transaction.category_id)
        if not category:
            raise ValueError("Category not found")
        # Delegate to repository
        return self._transaction_repo.create(transaction_data)
```

The DI wiring in `dependencies.py`:

```python
from fastapi import Depends
from backend.repositories import get_transaction_repository, get_category_repository

def get_transaction_service(db: Session = Depends(get_db)) -> TransactionService:
    return TransactionService(
        transaction_repo=get_transaction_repository(db),
        category_repo=get_category_repository(db),
        planned_transaction_repo=get_planned_transaction_repository(db),
    )
```

Routes use it via `Depends()`:

```python
@router.post("/", status_code=201)
def create_transaction(
    transaction: TransactionCreate,
    service: TransactionService = Depends(get_transaction_service),
    account_id: int = Depends(get_account_id_from_headers),
):
    return service.create_transaction(transaction)
```

### Process Flow: Database Selection

```mermaid
flowchart TD
    A[Request Arrives] --> B{ACTIVE_DB in .env?}
    B -->|mysql| C[MySQL Repository]
    B -->|elasticsearch| D[Elasticsearch Repository]
    B -->|neo4j| E[Neo4j Repository]
    
    C --> F[SQLAlchemy Session]
    D --> G[Elasticsearch Client]
    E --> H[Neo4j Driver]
    
    F --> I[Execute SQL Query]
    G --> J[Execute ES Query]
    H --> K[Execute Cypher Query]
    
    I --> L[Return Results]
    J --> L
    K --> L
```

### Authentication Flow

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant Backend
    participant UserService
    participant UserRepo as User Repository
    participant Auth as auth.py

    User->>Frontend: Enter credentials
    Frontend->>Backend: POST /users/login
    Backend->>UserService: login_user(username, password)
    UserService->>UserRepo: get_by_username(username)
    UserRepo-->>UserService: User data (with hashed password)
    UserService->>Auth: verify_password(plain, hashed)
    Auth->>Auth: bcrypt.checkpw()
    alt Password valid
        UserService->>Auth: create_access_token(user_id, username, email)
        Auth-->>UserService: JWT token
        UserService-->>Backend: TokenResponse
        Backend-->>Frontend: 200 OK + token
    else Password invalid
        UserService-->>Backend: ValueError
        Backend-->>Frontend: 401 Unauthorized
    end
```

### Multi-Database Support

The Repository Factory (`repositories/__init__.py`) selects implementations based on `ACTIVE_DB`:

```python
def get_transaction_repository(db: Session = None):
    if ACTIVE_DB == "mysql":
        return MySQLTransactionRepository(db)
    elif ACTIVE_DB == "elasticsearch":
        return ElasticsearchTransactionRepository()
    elif ACTIVE_DB == "neo4j":
        return Neo4jTransactionRepository()
```

Switch databases by changing one environment variable - no code changes needed:

| Variable | Database | Best For |
|----------|----------|----------|
| `ACTIVE_DB=mysql` | MySQL | ACID transactions, relational queries |
| `ACTIVE_DB=elasticsearch` | Elasticsearch | Full-text search, analytics |
| `ACTIVE_DB=neo4j` | Neo4j | Graph queries, relationship analysis |

---

## Security

### Authentication & Authorization

- **JWT Authentication** - Secure token-based authentication
  - Tokens expire after 24 hours
  - Include in `Authorization: Bearer <token>` header
- **Password Hashing** - bcrypt with 12 rounds
  - Passwords are never stored in plain text
  - Constant-time comparison prevents timing attacks
- **Protected Routes** - Authentication required for sensitive endpoints
  - Most endpoints require valid JWT token
  - Public endpoints: registration, login, health check
- **Account Isolation** - Users can only access their own data
  - Account context via `X-Account-ID` header
  - Server-side validation ensures data isolation

### Input Validation

- **Pydantic Schemas** - All inputs validated at API boundary
  - Type checking
  - Format validation
  - Business rule validation
- **SQL Injection Prevention** - Parameterized queries (SQLAlchemy)
- **XSS Prevention** - Output encoding in frontend

### Best Practices

- Never commit `.env` file with secrets
- Use strong `SECRET_KEY` in production
- Rotate JWT secrets periodically
- Use HTTPS in production

---

## Documentation

- [Installation Guide](INSTALLATION.md) - Setup instructions
- [Project Overview](backend/docs/PROJECT_OVERVIEW.md) - Architecture and flow
- [Project Status](backend/docs/PROJECT_STATUS.md) - What's implemented
- [Backend Readiness](backend/docs/BACKEND_READINESS.md) - Current status
- [Repository Pattern](backend/repositories/README.md) - Repository guide
- [Database Comparison](backend/DATABASE_COMPARISON.md) - Database details

---

## Development

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

# Run tests
set ACTIVE_DB=mysql
set SECRET_KEY=your-test-secret
pytest backend/tests/ -v
```

**Note:** When running locally, API is available at http://localhost:8000/docs (not 8080)

### Environment Variables

Create `.env` file in the project root:

```bash
# =============================================================================
# Database Configuration
# =============================================================================

# Active database: mysql, elasticsearch, or neo4j
ACTIVE_DB=mysql

# MySQL Configuration
DATABASE_URL=mysql+pymysql://root:123456@localhost:3307/finans_tracker

# Elasticsearch Configuration
ELASTICSEARCH_HOST=http://localhost:9200

# Neo4j Configuration
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=12345678

# =============================================================================
# Security
# =============================================================================

# JWT Secret Key (generate with: openssl rand -hex 32)
SECRET_KEY=your-secret-key-here-change-in-production

# =============================================================================
# Application Settings
# =============================================================================

# CORS Origins (comma-separated)
CORS_ORIGINS=http://localhost:3000,http://localhost:3001
```

**Required Variables:**
- `ACTIVE_DB` - Database to use (mysql/elasticsearch/neo4j)
- `SECRET_KEY` - JWT signing key (required for authentication)

**Database-Specific Variables:**
- MySQL: `DATABASE_URL` (required when `ACTIVE_DB=mysql`)
- Elasticsearch: `ELASTICSEARCH_HOST` (required when `ACTIVE_DB=elasticsearch`)
- Neo4j: `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` (required when `ACTIVE_DB=neo4j`)

---

## Troubleshooting

See [INSTALLATION.md](INSTALLATION.md#-troubleshooting) for common issues and solutions.

---

## License

MIT License - See LICENSE file for details

---

## Acknowledgments

- **FastAPI** - Modern Python web framework
- **SQLAlchemy** - Python SQL toolkit
- **Elasticsearch** - Search and analytics engine
- **Neo4j** - Graph database
- **React** - Frontend framework

---

## Roadmap

- [x] Clean Architecture with Repository Pattern
- [x] Class-based services with Dependency Injection
- [x] Unit tests for all services (150 tests)
- [x] Integration tests for all major flows (30 tests)
- [x] Schema validation tests with BVA (141 tests)
- [x] JWT authentication with bcrypt
- [x] Planned transactions merged into TransactionService
- [x] Account groups merged into AccountService
- [ ] Hexagonal Architecture (ports and adapters)
- [ ] Database migrations with Alembic
- [ ] Rate limiting and security hardening
- [ ] Export functionality (PDF, Excel)
- [ ] Notifications and alerts
- [ ] E2E tests with Playwright
- [ ] Microservice extraction

---

## Contact

For questions or issues, please open an issue on GitHub.

---

**Built with Clean Architecture, Repository Pattern, and Dependency Injection**

