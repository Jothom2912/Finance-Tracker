# Repository Pattern - Komplet Oversigt

## 🎯 Hvad er Repository Pattern?

Repository Pattern er en design pattern der abstraherer data access laget. I stedet for at kode direkte mod MySQL, Elasticsearch eller Neo4j, bruger vi repositories der giver samme interface uanset hvilken database der bruges.

## 📐 Arkitektur Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    FastAPI Routes                        │
│              (routers/transactions.py)                  │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│              Repository Factory                         │
│    (repositories/__init__.py)                           │
│                                                         │
│    get_transaction_repository()                        │
│    ↓                                                    │
│    Tjekker ACTIVE_DB i .env                            │
└───────┬───────────────┬───────────────┬─────────────────┘
        │               │               │
        ▼               ▼               ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│   MySQL      │ │ Elasticsearch│ │    Neo4j     │
│ Repository   │ │ Repository   │ │ Repository   │
└──────┬───────┘ └──────┬───────┘ └──────┬──────┘
       │                 │                 │
       ▼                 ▼                 ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│   MySQL      │ │ Elasticsearch│ │    Neo4j     │
│  Database    │ │   Cluster    │ │   Database   │
└──────────────┘ └──────────────┘ └──────────────┘
```

## 🔄 Data Flow

### 1. Request kommer ind
```python
# I router (f.eks. routers/transactions.py)
@router.get("/")
def get_transactions():
    repo = get_transaction_repository()  # ← Factory vælger repository
    return repo.get_all()                # ← Samme interface!
```

### 2. Factory vælger repository
```python
# repositories/__init__.py
def get_transaction_repository():
    if ACTIVE_DB == "mysql":
        return MySQLTransactionRepository()
    elif ACTIVE_DB == "elasticsearch":
        return ElasticsearchTransactionRepository()
    elif ACTIVE_DB == "neo4j":
        return Neo4jTransactionRepository()
```

### 3. Repository eksekverer query
- **MySQL**: SQL query via SQLAlchemy
- **Elasticsearch**: Query DSL (JSON)
- **Neo4j**: Cypher query

### 4. Data returneres
Alle repositories returnerer samme format (Dict/List[Dict])

## 📋 Interface Kontrakt

Alle repositories implementerer samme interface fra `base.py`:

```python
class ITransactionRepository(ABC):
    def get_all(...) -> List[Dict]
    def get_by_id(id: int) -> Optional[Dict]
    def create(data: Dict) -> Dict
    def update(id: int, data: Dict) -> Dict
    def delete(id: int) -> bool
    def search(...) -> List[Dict]
    def get_summary_by_category(...) -> Dict
```

**Fordel:** Koden der bruger repositories behøver ikke at vide hvilken database der bruges!

## 🗂️ Mappe Struktur

```
repositories/
├── __init__.py                    # Factory functions
├── base.py                        # Abstract interfaces
│
├── mysql/                         # MySQL implementations
│   ├── __init__.py
│   ├── transaction_repository.py
│   ├── category_repository.py
│   ├── account_repository.py
│   ├── user_repository.py
│   ├── budget_repository.py
│   └── goal_repository.py
│
├── elasticsearch/                 # Elasticsearch implementations
│   ├── __init__.py
│   ├── transaction_repository.py
│   └── category_repository.py
│
└── neo4j/                         # Neo4j implementations
    ├── __init__.py
    ├── transaction_repository.py
    ├── category_repository.py
    ├── account_repository.py
    └── user_repository.py
```

## 💻 Eksempel: Hvordan det virker

### Scenario: Hent alle transaktioner

**1. I din router/service:**
```python
from backend.repositories import get_transaction_repository

def get_all_transactions():
    repo = get_transaction_repository()  # ← Automatisk valg
    return repo.get_all(account_id=1)    # ← Samme kode!
```

**2. Hvis ACTIVE_DB=mysql:**
```python
# Factory returnerer MySQLTransactionRepository
repo = MySQLTransactionRepository()

# Eksekverer SQL:
# SELECT * FROM Transaction WHERE Account_idAccount = 1
```

**3. Hvis ACTIVE_DB=elasticsearch:**
```python
# Factory returnerer ElasticsearchTransactionRepository
repo = ElasticsearchTransactionRepository()

# Eksekverer Elasticsearch query:
# {"query": {"term": {"Account_idAccount": 1}}}
```

**4. Hvis ACTIVE_DB=neo4j:**
```python
# Factory returnerer Neo4jTransactionRepository
repo = Neo4jTransactionRepository()

# Eksekverer Cypher:
# MATCH (a:Account {idAccount: 1})-[:HAS_TRANSACTION]->(t:Transaction)
# RETURN t
```

**Resultat:** Samme interface, forskellige databaser! 🎯

## 🔧 Sådan skifter du database

### Metode 1: Environment Variable (Anbefalet)

I `.env` filen:
```bash
# Skift til MySQL
ACTIVE_DB=mysql

# Skift til Elasticsearch
ACTIVE_DB=elasticsearch

# Skift til Neo4j
ACTIVE_DB=neo4j
```

Genstart FastAPI serveren - den læser automatisk den nye værdi!

### Metode 2: Direkte i kode (Test/Development)

```python
from backend.config import DatabaseType
from backend.repositories.mysql.transaction_repository import MySQLTransactionRepository

# Brug specifik repository direkte
repo = MySQLTransactionRepository()
```

## 📊 Repository Support Matrix

| Repository | MySQL | Elasticsearch | Neo4j |
|------------|-------|---------------|-------|
| Transaction | ✅ | ✅ | ✅ |
| Category | ✅ | ✅ | ✅ |
| Account | ✅ | ❌ | ✅ |
| User | ✅ | ❌ | ✅ |
| Budget | ✅ | ❌ | ❌ |
| Goal | ✅ | ❌ | ❌ |

**Forklaring:**
- **MySQL**: Fuld support for alle entities (primær database)
- **Elasticsearch**: Kun Transaction og Category (søgning/analytics)
- **Neo4j**: Transaction, Category, Account, User (graph queries)

## 🎨 Design Principper

### 1. **Separation of Concerns**
- Hver database har sin egen mappe
- Klar adskillelse mellem implementations

### 2. **Dependency Inversion**
- Kode afhænger af interfaces, ikke konkrete implementations
- Nemt at bytte database uden at ændre business logic

### 3. **Single Responsibility**
- Hver repository håndterer én entity type
- Klar ansvarsfordeling

### 4. **Open/Closed Principle**
- Åben for udvidelse (tilføj ny database)
- Lukket for modificering (eksisterende kode ændres ikke)

## 🔍 Eksempel: Komplet Flow

### Request: `GET /transactions/?account_id=1`

```python
# 1. Router modtager request
@router.get("/")
def get_transactions(account_id: int):
    # 2. Hent repository (factory pattern)
    repo = get_transaction_repository()
    
    # 3. Brug repository (samme interface!)
    transactions = repo.get_all(account_id=account_id)
    
    # 4. Returner response
    return transactions
```

**Hvis ACTIVE_DB=mysql:**
```
Router → Factory → MySQLTransactionRepository → SQLAlchemy → MySQL
                                                              ↓
Response ← Router ← Factory ← MySQLTransactionRepository ← Data
```

**Hvis ACTIVE_DB=elasticsearch:**
```
Router → Factory → ElasticsearchTransactionRepository → Elasticsearch Client → ES
                                                              ↓
Response ← Router ← Factory ← ElasticsearchTransactionRepository ← Data
```

**Hvis ACTIVE_DB=neo4j:**
```
Router → Factory → Neo4jTransactionRepository → Neo4j Driver → Neo4j
                                                              ↓
Response ← Router ← Factory ← Neo4jTransactionRepository ← Data
```

## ✅ Fordele

1. **Nemt at skifte database** - Én environment variable
2. **Samme interface** - Ingen kodeændringer nødvendige
3. **Testbar** - Nemt at mocke repositories
4. **Skalerbar** - Tilføj ny database uden at ændre eksisterende kode
5. **Klar struktur** - Nemt at finde og forstå kode

## 🚀 Næste Skridt

1. **Brug repositories i dine services:**
   ```python
   from backend.repositories import get_transaction_repository
   repo = get_transaction_repository()
   ```

2. **Test med forskellige databaser:**
   ```bash
   # Test MySQL
   ACTIVE_DB=mysql python -m uvicorn backend.main:app
   
   # Test Elasticsearch
   ACTIVE_DB=elasticsearch python -m uvicorn backend.main:app
   
   # Test Neo4j
   ACTIVE_DB=neo4j python -m uvicorn backend.main:app
   ```

3. **Tilføj flere repositories** hvis nødvendigt (f.eks. Budget til Elasticsearch)

## 📚 Se også

- `README.md` - Detaljeret guide
- `MIGRATION_GUIDE.md` - Hvordan man migrerer fra gammel struktur
- `base.py` - Alle interfaces

