# 📚 Projekt Oversigt - Hvordan Fungerer Det?

## 🎯 Projekt Formål

Dette er en **Personlig Finans Tracker** backend API, der giver dig mulighed for at:
- 📊 Tracke dine indtægter og udgifter
- 💰 Sætte budgetter og mål
- 📈 Få finansiel oversigt og analytics
- 🔍 Søge i transaktioner
- 👥 Håndtere flere konti og brugere

---

## 🏗️ Arkitektur Oversigt

Projektet følger en **Clean Architecture** med klart adskilte lag:

```
┌─────────────────────────────────────────────────────────┐
│                    FRONTEND (React)                      │
│  - React Components                                       │
│  - API Client (apiClient.js)                             │
│  - Authentication Context                                │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP Requests (JSON)
                       │ JWT Token Authentication
                       │ X-Account-ID Header
┌──────────────────────▼──────────────────────────────────┐
│              BACKEND (FastAPI)                          │
│                                                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │  ROUTES LAYER (API Endpoints)                     │  │
│  │  - /users/     - /accounts/  - /transactions/    │  │
│  │  - /categories/ - /budgets/  - /goals/           │  │
│  │  - /dashboard/ - /account_groups/                │  │
│  └──────────────┬───────────────────────────────────┘  │
│                 │                                       │
│  ┌──────────────▼───────────────────────────────────┐  │
│  │  SERVICES LAYER (Business Logic)                 │  │
│  │  - user_service.py      - transaction_service.py │  │
│  │  - account_service.py   - budget_service.py      │  │
│  │  - dashboard_service.py - categorization.py     │  │
│  └──────────────┬───────────────────────────────────┘  │
│                 │                                       │
│  ┌──────────────▼───────────────────────────────────┐  │
│  │  REPOSITORY LAYER (Data Access)                  │  │
│  │  ┌──────────┬──────────┬──────────┐              │  │
│  │  │  MySQL   │Elastic- │  Neo4j   │              │  │
│  │  │          │ search   │          │              │  │
│  │  └──────────┴──────────┴──────────┘              │  │
│  │  Factory Pattern - Vælg database dynamisk        │  │
│  └───────────────────────────────────────────────────┘  │
└──────────────────────┬──────────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
┌───────▼──────┐ ┌─────▼──────┐ ┌─────▼──────┐
│    MySQL     │ │Elasticsearch│ │   Neo4j   │
│  (Primary)   │ │  (Search)   │ │  (Graph)  │
└──────────────┘ └─────────────┘ └──────────┘
```

---

## 🔄 Data Flow - Eksempel: Opret Transaktion

### 1. **Frontend Request**
```javascript
// Frontend sender request via apiClient
apiClient.post('/transactions/', {
  amount: -500.00,
  description: "Netto køb",
  date: "2024-12-15",
  type: "expense",
  Category_idCategory: 3
})
```

### 2. **API Route Handler**
```python
# backend/routes/transactions.py
@router.post("/", response_model=TransactionSchema)
def create_transaction_route(
    transaction: TransactionCreate,
    account_id: int = Depends(get_account_id_from_headers),
    current_user_id: int = Depends(get_current_user_id)
):
    # Validerer input, henter account_id fra header
    return transaction_service.create_transaction(db, transaction, account_id)
```

### 3. **Service Layer (Business Logic)**
```python
# backend/services/transaction_service.py
def create_transaction(db: Session, transaction: TransactionCreate, account_id: int):
    # Business logic:
    # - Validerer at account eksisterer
    # - Validerer at category eksisterer
    # - Opretter transaction via repository
    repo = get_transaction_repository(db)  # ← Pass session for MySQL
    return repo.create(transaction_data)
```

### 4. **Repository Layer (Data Access)**
```python
# backend/repositories/mysql/transaction_repository.py
# ELLER
# backend/repositories/elasticsearch/transaction_repository.py
# ELLER
# backend/repositories/neo4j/transaction_repository.py

class MySQLTransactionRepository:
    def create(self, transaction_data: Dict):
        # SQLAlchemy ORM
        transaction = TransactionModel(**transaction_data)
        db.add(transaction)
        db.commit()
        return transaction
```

### 5. **Database**
- **MySQL**: Gemmer i `Transaction` tabel
- **Elasticsearch**: Gemmer som dokument i `transactions` index
- **Neo4j**: Opretter node og relationships

---

## 🔐 Authentication Flow

### Login Process

```
1. User indtaster username/password
   ↓
2. Frontend: POST /users/login
   ↓
3. Backend: Verificerer password (bcrypt)
   ↓
4. Backend: Genererer JWT token
   ↓
5. Frontend: Gemmer token i localStorage
   ↓
6. Frontend: Inkluderer token i alle requests
   Authorization: Bearer <token>
```

### Protected Routes

```python
# Backend route med authentication
@router.get("/transactions/")
def get_transactions(
    current_user_id: int = Depends(get_current_user_id)  # ← Validerer token
):
    # Kun hvis token er valid, kommer vi hertil
    return get_transactions_for_user(current_user_id)
```

---

## 🗄️ Multi-Database Support

### Repository Pattern

Projektet bruger **Repository Pattern** for at abstrahere database-detaljer:

```python
# ✅ FastAPI Routes (med session management)
from fastapi import Depends
from sqlalchemy.orm import Session
from backend.database.mysql import get_db
from backend.repositories import get_transaction_repository

@router.get("/")
def get_transactions(db: Session = Depends(get_db)):
    repo = get_transaction_repository(db)  # ← Pass session for MySQL
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

**Note:** MySQL repositories kræver session, Elasticsearch og Neo4j repositories virker uden session.

### Database Valg

Skift database via `.env` fil:
```bash
# MySQL (standard)
ACTIVE_DB=mysql

# Elasticsearch (søgning/analytics)
ACTIVE_DB=elasticsearch

# Neo4j (graph queries)
ACTIVE_DB=neo4j
```

### Hvornår Bruges Hvilken Database?

| Database | Brug Til | Styrker |
|----------|----------|---------|
| **MySQL** | Primær database, CRUD operations | ACID, Relations, Mature |
| **Elasticsearch** | Søgning, Analytics, Full-text search | Hurtig søgning, Aggregations |
| **Neo4j** | Graph queries, Relationships | Graph traversals, Connections |

---

## 📁 Projekt Struktur

```
backend/
├── main.py                    # FastAPI app entry point
├── config.py                  # Konfiguration (ACTIVE_DB, etc.)
├── auth.py                    # JWT + password hashing
│
├── shared/                    # Delt på tværs af alt
│   ├── schemas/              # Pydantic schemas (validation)
│   │   ├── user.py
│   │   ├── transaction.py
│   │   └── ...
│   └── exceptions/           # Custom exceptions
│
├── database/                  # Database connections
│   ├── mysql.py             # SQLAlchemy setup
│   ├── elasticsearch.py     # ES client
│   └── neo4j.py             # Neo4j driver
│
├── models/                    # Database models
│   ├── mysql/                # SQLAlchemy models
│   ├── elasticsearch/        # ES mappings (tom)
│   └── neo4j/               # Cypher templates (tom)
│
├── repositories/              # 🎯 REPOSITORY PATTERN
│   ├── base.py              # Abstract interfaces
│   ├── __init__.py          # Factory functions
│   ├── mysql/               # MySQL implementations
│   ├── elasticsearch/       # Elasticsearch implementations
│   └── neo4j/               # Neo4j implementations
│
├── services/                  # Business logic
│   ├── user_service.py
│   ├── transaction_service.py
│   ├── budget_service.py
│   └── ...
│
├── routes/                    # FastAPI routers
│   ├── users.py
│   ├── transactions.py
│   ├── accounts.py
│   └── ...
│
└── migrations/                # Database migrations
    ├── elasticsearch/
    └── neo4j/
```

---

## 🔑 Vigtige Koncepter

### 0. **Session Management**

Applikationen bruger FastAPI's dependency injection til database sessions:

**FastAPI Routes:**
```python
from fastapi import Depends
from sqlalchemy.orm import Session
from backend.database.mysql import get_db
from backend.repositories import get_transaction_repository

@router.get("/")
def get_transactions(db: Session = Depends(get_db)):
    # Session lukkes automatisk efter request
    repo = get_transaction_repository(db)
    return repo.get_all()
```

**Services:**
```python
def get_transactions(db: Session, account_id: int):
    # Modtag session som parameter
    repo = get_transaction_repository(db)
    return repo.get_all(account_id=account_id)
```

**Scripts:**
```python
from backend.database.mysql import SessionLocal
from backend.repositories import get_transaction_repository
from backend.config import ACTIVE_DB

db = SessionLocal() if ACTIVE_DB == "mysql" else None
try:
    repo = get_transaction_repository(db) if ACTIVE_DB == "mysql" else get_transaction_repository()
    transactions = repo.get_all()
finally:
    if db:
        db.close()  # Vigtigt: Luk session manuelt i scripts
```

**Vigtigt:**
- ✅ MySQL repositories kræver session
- ✅ Elasticsearch og Neo4j repositories virker uden session
- ✅ FastAPI lukker sessions automatisk efter request
- ✅ Scripts skal lukke sessions manuelt i `finally` blok

### 1. **Repository Pattern**

**Problem:** Hvordan skifter man database uden at ændre business logic?

**Løsning:** Repository Pattern med interfaces:

```python
# Interface (kontrakt)
class ITransactionRepository(ABC):
    @abstractmethod
    def get_all(self, account_id: int) -> List[Dict]:
        pass

# Implementations
class MySQLTransactionRepository(ITransactionRepository):
    def get_all(self, account_id: int):
        # SQLAlchemy query
        ...

class ElasticsearchTransactionRepository(ITransactionRepository):
    def get_all(self, account_id: int):
        # Elasticsearch query
        ...

# Factory vælger implementation
def get_transaction_repository():
    if ACTIVE_DB == "mysql":
        return MySQLTransactionRepository()
    elif ACTIVE_DB == "elasticsearch":
        return ElasticsearchTransactionRepository()
```

**Fordel:** Business logic (services) behøver ikke at vide hvilken database der bruges!

### 2. **Dependency Injection & Session Management**

FastAPI bruger dependency injection for at håndtere:
- Database sessions (automatisk lukning efter request)
- Authentication
- Account ID fra headers

```python
@router.get("/transactions/")
def get_transactions(
    db: Session = Depends(get_db),                    # ← Dependency (auto-closed after request)
    account_id: int = Depends(get_account_id_from_headers),  # ← Dependency
    current_user_id: int = Depends(get_current_user_id)       # ← Dependency
):
    # FastAPI håndterer automatisk at kalde disse funktioner
    # Session lukkes automatisk efter request
    repo = get_transaction_repository(db)  # Pass session to repository
    return repo.get_all(account_id=account_id)
```

**Session Management:**
- **Routes:** Use `db: Session = Depends(get_db)` - session lukkes automatisk
- **Services:** Receive `db: Session` as parameter
- **Repositories:** MySQL repositories require session, Elasticsearch/Neo4j don't
- **Scripts:** Manually create and close session with `SessionLocal()` and `db.close()`

### 3. **Account Context**

Alle transaktioner, budgetter, etc. er knyttet til en **Account**:

```python
# Frontend sender account_id i header
X-Account-ID: 1

# Backend henter det automatisk
account_id = get_account_id_from_headers(request)

# Filterer data efter account
transactions = get_transactions(account_id=account_id)
```

**Fordel:** En bruger kan have flere konti (fx "Privat", "Fælles", "Opsparing")

---

## 🔄 Typiske Flows

### Flow 1: Opret Bruger

```
1. User registrerer sig
   POST /users/
   {username, email, password}
   ↓
2. Backend hasher password (bcrypt)
   ↓
3. Opretter User i database
   ↓
4. Opretter automatisk default Account ("Min Konto")
   ↓
5. Returnerer User (uden password)
   ↓
6. Frontend redirecter til login
```

### Flow 2: Login

```
1. User logger ind
   POST /users/login
   {username_or_email, password}
   ↓
2. Backend finder user
   ↓
3. Verificerer password (bcrypt.checkpw)
   ↓
4. Genererer JWT token
   ↓
5. Returnerer token + account_id
   ↓
6. Frontend gemmer token
   ↓
7. Frontend redirecter til dashboard
```

### Flow 3: Upload CSV

```
1. User uploader CSV fil
   POST /transactions/upload-csv/
   FormData: {file: CSV}
   ↓
2. Backend parser CSV (pandas)
   ↓
3. For hver række:
   - Find eller opret Category
   - Opret Transaction
   - Link til Account (fra X-Account-ID header)
   ↓
4. Returnerer antal importerede transaktioner
```

### Flow 4: Dashboard Overview

```
1. Frontend: GET /dashboard/overview/
   ↓
2. Backend henter:
   - Total income (SUM hvor type='income')
   - Total expenses (SUM hvor type='expense')
   - Net balance (income - expenses)
   - Transaction count
   - Average transaction
   ↓
3. Brug database-side aggregation (func.sum, func.count)
   ↓
4. Returnerer JSON med statistics
```

---

## 🛠️ Vigtige Filer

### `backend/main.py`
- FastAPI app entry point
- CORS konfiguration
- Router registration
- Health check endpoint

### `backend/config.py`
- Environment variables
- Database type konfiguration
- `ACTIVE_DB` setting

### `backend/auth.py`
- Password hashing (bcrypt)
- JWT token generation/validation
- `get_current_user_id` dependency

### `backend/repositories/__init__.py`
- Factory functions
- Vælger repository implementation baseret på `ACTIVE_DB`

### `backend/services/*.py`
- Business logic
- Validering
- Data transformation
- Bruger repositories (ikke direkte database)

### `backend/routes/*.py`
- API endpoints
- Request/response handling
- Authentication
- Bruger services (ikke direkte repositories)

---

## 🔍 Sådan Finder Du Kode

### "Hvor oprettes en transaction?"
1. Route: `backend/routes/transactions.py` → `create_transaction_route`
2. Service: `backend/services/transaction_service.py` → `create_transaction`
3. Repository: `backend/repositories/mysql/transaction_repository.py` → `create`

### "Hvor valideres password?"
1. `backend/auth.py` → `verify_password`
2. `backend/services/user_service.py` → `login_user`

### "Hvor skifter jeg database?"
1. `.env` fil → `ACTIVE_DB=mysql|elasticsearch|neo4j`
2. `backend/repositories/__init__.py` → Factory functions vælger automatisk

---

## 🎯 Best Practices i Projektet

### 1. **Separation of Concerns**
- Routes: Kun HTTP handling
- Services: Business logic
- Repositories: Data access

### 2. **Dependency Injection**
- FastAPI dependencies for database, auth, etc.
- Nemt at teste (kan mocke dependencies)

### 3. **Type Safety**
- Pydantic schemas for validation
- Type hints overalt
- Interfaces for repositories

### 4. **Error Handling**
- Try/except blocks
- HTTP status codes
- Meaningful error messages

### 5. **Security**
- Password hashing (bcrypt)
- JWT tokens
- Protected routes
- Account isolation

---

## 🚀 Sådan Starter Du Projektet

### 1. **Backend**
```bash
cd backend
python -m uvicorn backend.main:app --reload --port 8000
```

### 2. **Frontend**
```bash
cd frontend/finans-tracker-frontend
npm start
```

### 3. **Database Setup**
- MySQL: Kør migrations eller lad SQLAlchemy oprette tabeller
- Elasticsearch: Indices oprettes automatisk
- Neo4j: Constraints oprettes ved migration

---

## 📊 Data Model (Simplificeret)

```
User
  ├── Account (1:N)
  │     ├── Transaction (1:N)
  │     │     └── Category (N:1)
  │     ├── Budget (1:N)
  │     └── Goal (1:N)
  └── AccountGroup (M:N)
```

**Relationships:**
- User → Account: En bruger kan have flere konti
- Account → Transaction: En konto har mange transaktioner
- Transaction → Category: En transaktion tilhører én kategori
- Account → Budget: En konto kan have flere budgetter
- Account → Goal: En konto kan have flere mål

---

## 🎓 Læringspunkter

### Repository Pattern
- Abstraherer database-detaljer
- Nemt at skifte database
- Testbar (kan mocke repositories)

### Dependency Injection
- Løs kobling mellem komponenter
- Nemt at teste
- FastAPI håndterer det automatisk

### Clean Architecture
- Klar separation of concerns
- Nemt at vedligeholde
- Skalerbar struktur

---

## 🔗 Relaterede Dokumenter

- `PROJECT_STATUS.md` - Hvad er implementeret, hvad mangler
- `STRUCTURE.md` - Detaljeret struktur guide
- `TROUBLESHOOTING_SUMMARY.md` - Fejlfinding guide
- `repositories/README.md` - Repository pattern guide

---

**Dette projekt demonstrerer:**
- ✅ Clean Architecture
- ✅ Repository Pattern
- ✅ Multi-database support
- ✅ Authentication & Authorization
- ✅ RESTful API design
- ✅ Type safety med Pydantic
- ✅ Dependency Injection

**Tillykke med et velstruktureret projekt! 🎉**

