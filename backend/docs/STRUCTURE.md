# Backend Struktur Guide

## 📁 Mappestruktur

```
backend/
├── main.py                          # FastAPI app entry point
├── config.py                        # ACTIVE_DB configuration
├── requirements.txt
│
├── shared/                          # Delt på tværs af alt
│   ├── __init__.py
│   ├── schemas/                     # Pydantic schemas (bruges overalt)
│   │   ├── __init__.py
│   │   ├── transaction.py
│   │   ├── account.py
│   │   ├── category.py
│   │   ├── user.py
│   │   ├── budget.py
│   │   └── goal.py
│   │
│   └── exceptions/
│       ├── __init__.py
│       └── business_exceptions.py
│
├── database/                        # Database connections
│   ├── __init__.py                 # Re-exports for backward compatibility
│   ├── mysql.py                    # MySQL SessionLocal & Base
│   ├── elasticsearch.py            # ES client
│   └── neo4j.py                    # Neo4j driver
│
├── models/                          # Database-specifik models
│   ├── __init__.py                 # Re-exports MySQL models
│   │
│   ├── mysql/                      # SQLAlchemy models
│   │   ├── __init__.py
│   │   ├── transaction.py
│   │   ├── account.py
│   │   ├── category.py
│   │   ├── user.py
│   │   ├── budget.py
│   │   ├── goal.py
│   │   ├── account_groups.py
│   │   ├── planned_transactions.py
│   │   └── common.py
│   │
│   ├── elasticsearch/              # ES mappings (fremtidig)
│   │   └── __init__.py
│   │
│   └── neo4j/                      # Cypher query templates (fremtidig)
│       └── __init__.py
│
├── repositories/                    # 🎯 REPOSITORY PATTERN (hjertet!)
│   ├── __init__.py                 # Factory functions
│   ├── base.py                     # Abstract interfaces (ABC)
│   │
│   ├── mysql/                      # MySQL implementations
│   │   ├── __init__.py
│   │   ├── transaction_repository.py
│   │   ├── account_repository.py
│   │   ├── category_repository.py
│   │   ├── user_repository.py
│   │   ├── budget_repository.py
│   │   └── goal_repository.py
│   │
│   ├── elasticsearch/              # Elasticsearch implementations
│   │   ├── __init__.py
│   │   ├── transaction_repository.py
│   │   └── category_repository.py
│   │
│   └── neo4j/                      # Neo4j implementations
│       ├── __init__.py
│       ├── transaction_repository.py
│       ├── account_repository.py
│       ├── category_repository.py
│       └── user_repository.py
│
├── services/                        # Business logic (database-agnostic!)
│   ├── __init__.py
│   ├── transaction_service.py      # Bruger repositories via factory
│   ├── account_service.py
│   ├── category_service.py
│   ├── user_service.py
│   └── budget_service.py
│
├── routes/                          # FastAPI routers (database-agnostic!)
│   ├── __init__.py
│   ├── transactions.py             # ÉN route fil for alle 3 DBs
│   ├── accounts.py
│   ├── categories.py
│   ├── users.py
│   ├── budgets.py
│   └── search.py                   # Special routes (ES-specifik features)
│
├── migrations/                      # Database migrations
│   ├── mysql/
│   │   └── (fremtidig: alembic)
│   ├── elasticsearch/
│   │   └── migrate_to_elasticsearch.py
│   └── neo4j/
│       └── migrate_to_neo4j.py
│
├── tests/
│   ├── __init__.py
│   ├── test_repositories/          # Test repositories med mock data
│   ├── test_services/
│   └── test_routes/
│
└── docs/
    ├── STRUCTURE.md                 # Denne fil
    ├── REPOSITORY_PATTERN.md
    └── database_comparison.md
```

## 🔑 Vigtige Principper

### 1. **Separation of Concerns**
- Hver database har sin egen mappe
- Klar adskillelse mellem implementations

### 2. **Backward Compatibility**
- `database/__init__.py` re-exporterer `get_db`, `SessionLocal`, etc.
- `models/__init__.py` re-exporterer MySQL models
- Eksisterende kode virker stadig med `from backend.database import get_db`

### 3. **Repository Pattern**
- Alle database operations går gennem repositories
- Factory pattern vælger automatisk korrekt implementation baseret på `ACTIVE_DB`

### 4. **Shared Resources**
- `shared/schemas/` - Pydantic schemas delt på tværs af databaser
- `shared/exceptions/` - Custom exceptions for business logic

## 📝 Import Eksempler

### Database Connections
```python
# MySQL (standard)
from backend.database import get_db, SessionLocal, Base

# Eller specifikt
from backend.database.mysql import get_db, SessionLocal, Base

# Elasticsearch
from backend.database.elasticsearch import get_es_client

# Neo4j
from backend.database.neo4j import get_neo4j_driver
```

### Models
```python
# MySQL models (standard)
from backend.models import User, Transaction, Category

# Eller specifikt
from backend.models.mysql import User, Transaction, Category
```

### Schemas
```python
from backend.shared.schemas.transaction import TransactionCreate
from backend.shared.schemas.user import UserCreate
```

### Repositories
```python
from backend.repositories import get_transaction_repository

repo = get_transaction_repository()  # Automatisk valg baseret på ACTIVE_DB
```

### Routes
```python
from backend.routes import transactions, accounts, users
```

## 🚀 Migration fra gammel struktur

Alle imports er opdateret, men hvis du støder på problemer:

1. **Database imports**: Brug `from backend.database import ...` (virker stadig)
2. **Model imports**: Brug `from backend.models import ...` (virker stadig)
3. **Schema imports**: Opdater til `from backend.shared.schemas import ...`
4. **Route imports**: Opdater til `from backend.routes import ...`

## ✅ Status

- ✅ Mappestruktur oprettet
- ✅ Database connections refactored
- ✅ Models flyttet til `models/mysql/`
- ✅ Schemas flyttet til `shared/schemas/`
- ✅ Routes flyttet fra `routers/` til `routes/`
- ✅ Migrations organiseret
- ✅ Alle imports opdateret
- ✅ Backward compatibility sikret

