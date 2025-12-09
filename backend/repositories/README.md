# Repository Pattern - Multi-Database Support

Denne mappe indeholder repository implementations for alle 3 databaser: MySQL, Elasticsearch og Neo4j.

## 📁 Mappe Struktur

```
repositories/
├── __init__.py              # Factory functions til at vælge repository
├── base.py                  # Abstract interfaces (kontrakter)
├── mysql/                   # MySQL implementations
│   ├── transaction_repository.py
│   ├── category_repository.py
│   ├── account_repository.py
│   ├── user_repository.py
│   ├── budget_repository.py
│   └── goal_repository.py
├── elasticsearch/           # Elasticsearch implementations
│   ├── transaction_repository.py
│   └── category_repository.py
└── neo4j/                   # Neo4j implementations
    ├── transaction_repository.py
    ├── category_repository.py
    ├── account_repository.py
    └── user_repository.py
```

## 🔄 Sådan skifter du database

### Via Environment Variable

I `.env` filen:

```bash
# Brug MySQL (standard)
ACTIVE_DB=mysql

# Brug Elasticsearch
ACTIVE_DB=elasticsearch

# Brug Neo4j
ACTIVE_DB=neo4j
```

### I Koden

```python
from backend.repositories import get_transaction_repository

# Henter automatisk den rigtige repository baseret på ACTIVE_DB
repo = get_transaction_repository()

# Brug repository - samme interface uanset database!
transactions = repo.get_all(start_date=date(2024, 1, 1))
```

## 📋 Repository Interfaces

Alle repositories implementerer de samme interfaces fra `base.py`:

- **ITransactionRepository** - CRUD for transaktioner
- **ICategoryRepository** - CRUD for kategorier
- **IAccountRepository** - CRUD for konti
- **IUserRepository** - CRUD for brugere
- **IBudgetRepository** - CRUD for budgetter
- **IGoalRepository** - CRUD for mål

## 🎯 Factory Functions

```python
from backend.repositories import (
    get_transaction_repository,
    get_category_repository,
    get_account_repository,
    get_user_repository,
    get_budget_repository,
    get_goal_repository
)

# Alle returnerer den rigtige implementation baseret på ACTIVE_DB
transaction_repo = get_transaction_repository()
category_repo = get_category_repository()
# osv...
```

## 💡 Eksempel Brug

```python
from backend.repositories import get_transaction_repository
from datetime import date

# Hent repository (automatisk valg baseret på ACTIVE_DB)
repo = get_transaction_repository()

# Brug samme interface uanset database
transactions = repo.get_all(
    start_date=date(2024, 1, 1),
    end_date=date(2024, 12, 31),
    account_id=1,
    limit=50
)

# Opret transaktion
new_transaction = repo.create({
    "idTransaction": 100,
    "amount": -500.0,
    "description": "Netto køb",
    "date": "2024-12-15",
    "type": "expense",
    "Category_idCategory": 1,
    "Account_idAccount": 1
})
```

## 🔧 Tilføj ny repository

1. Opret interface i `base.py` (hvis ikke eksisterer)
2. Implementer i alle 3 mapper:
   - `mysql/your_repository.py`
   - `elasticsearch/your_repository.py`
   - `neo4j/your_repository.py`
3. Tilføj factory function i `__init__.py`

## ✅ Fordele ved denne struktur

- ✅ **Separation of Concerns** - Hver database har sin egen mappe
- ✅ **Easy Switching** - Skift database med én environment variable
- ✅ **Type Safety** - Interfaces garanterer samme API
- ✅ **Testability** - Nemt at mocke repositories
- ✅ **Maintainability** - Klar struktur, nem at finde kode

