# Finance Tracker Backend API

En moderne FastAPI-baseret backend til et personligt økonomi-tracker system med support for både MySQL og Elasticsearch.

## 📋 Indholdsfortegnelse

- [Arkitektur](#arkitektur)
- [Hurtig Start](#hurtig-start)
- [Database Konfiguration](#database-konfiguration)
- [API Endpoints](#api-endpoints)
- [Repository Pattern](#repository-pattern)
- [Fejlfinding](#fejlfinding)

---

## 🏗️ Arkitektur

Projektet følger en **clean architecture** med klart adskilte lag:

```
backend/
├── main.py                          # FastAPI app entry point
├── config.py                        # Konfiguration (DatabaseType, env vars)
├── database.py                      # SQLAlchemy ORM modeller
├── routers/                         # API endpoints
│   ├── transactions.py              # Transaction CRUD routes
│   ├── categories.py                # Category management routes
│   ├── budgets.py                   # Budget routes
│   └── dashboard.py                 # Dashboard/analytics routes
├── repository/                      # Repository pattern (database abstraction)
│   ├── __init__.py                  # Factory functions
│   ├── base_repository.py           # Abstract interfaces
│   ├── mysql_repository.py          # MySQL implementation
│   └── elasticsearch_repository.py  # Elasticsearch implementation
├── schemas/                         # Pydantic request/response schemas
├── service/                         # Business logic
│   ├── categorization.py            # Auto-categorization logic
│   ├── elasticsearch_service.py     # Elasticsearch helpers
│   └── transactions_service.py      # Transaction business logic
└── migrate_to_elasticsearch.py      # Migration script (MySQL → ES)
```

### Arkitektur-diagram

```
┌─────────────────────────────────────┐
│      FastAPI Routes (routers/)      │
├─────────────────────────────────────┤
│   ITransactionRepository (interface)│
│   get_transaction_repository()      │
├──────────────────┬──────────────────┤
│  MySQLRepository │ ElasticsearchRepo│
├──────────────────┴──────────────────┤
│  MySQL (3307)   │ Elasticsearch    │
│                 │ (9200)           │
└─────────────────────────────────────┘
```

**Dataflow:**
1. Route modtager HTTP request
2. Factory function returnerer enten MySQL eller Elasticsearch repository
3. Repository udfører CRUD operation på valgt database
4. Response returneres til client

---

## 🚀 Hurtig Start

### Forudsætninger
- Python 3.10+
- Docker (for MySQL + Elasticsearch)
- pip/poetry

### Installation

1. **Opret virtual environment:**
   ```bash
   cd backend
   python -m venv venv
   # Windows
   venv\Scripts\activate
   # macOS/Linux
   source venv/bin/activate
   ```

2. **Installer dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Start Docker containers:**
   ```bash
   # MySQL
   docker run -d --name mysql \
     -e MYSQL_ROOT_PASSWORD=123456 \
     -p 3307:3306 \
     mysql:latest

   # Elasticsearch 7.17.0
   docker run -d --name elasticsearch \
     -e "discovery.type=single-node" \
     -e "xpack.security.enabled=false" \
     -e "ES_JAVA_OPTS=-Xms512m -Xmx512m" \
     -p 9200:9200 \
     docker.elastic.co/elasticsearch/elasticsearch:7.17.0

   # Kibana (opsjonalt - for Elasticsearch browse)
   docker run -d --name kibana \
     -p 5601:5601 \
     -e ELASTICSEARCH_HOSTS=http://host.docker.internal:9200 \
     docker.elastic.co/kibana/kibana:7.17.0
   ```

4. **Konfigurer `.env`:**
   ```bash
   DATABASE_URL=mysql+pymysql://root:123456@localhost:3307/finans_tracker?charset=utf8mb4
   ACTIVE_DB=mysql
   ELASTICSEARCH_HOST=http://localhost:9200
   SYNC_TO_ELASTICSEARCH=false
   ```

5. **Start backend:**
   ```bash
   python -m uvicorn backend.main:app --reload
   ```

   API kører på: **http://localhost:8000**

---

## 🗄️ Database Konfiguration

### MySQL (Standard)

**Status:** ✅ Primær database
**Port:** 3307 (mapped fra 3306)
**Database:** `finans_tracker`

**Tabeller:**
- `categories` - Transaktionskategorier (indtægter/udgifter)
- `transactions` - Alle finansielle transaktioner
- `budgets` - Månedlige budgetter pr. kategori

**Aktivering:**
```bash
# I .env
ACTIVE_DB=mysql
```

### Elasticsearch

**Status:** ✅ Sekundær database (analytics/søgning)
**Port:** 9200
**Version:** 7.17.0
**Indices:** `transactions`, `categories`

**Features:**
- Full-text søgning på `description`, `sender`, `recipient`
- Aggregationer og analyser
- Fuzzy matching

**Aktivering:**
```bash
# I .env
ACTIVE_DB=elasticsearch
```

### Skifte mellem databaser

Du kan skifte database på runtime ved at ændre `ACTIVE_DB` i `.env`:

```bash
# Brug MySQL
ACTIVE_DB=mysql

# Brug Elasticsearch
ACTIVE_DB=elasticsearch
```

Serveren genindlæser automatisk når den kører med `--reload`.

### Migration MySQL → Elasticsearch

For at migrere eksisterende data fra MySQL til Elasticsearch:

```bash
python -m backend.migrate_to_elasticsearch
```

**Output eksempel:**
```
✓ Elasticsearch status: green
✓ Oprettet index: transactions
Migrerer 67 transaktioner...
✓ Succesfuldt migreret 67 transaktioner til Elasticsearch
Total dokumenter i Elasticsearch: 67
```

---

## 🔌 API Endpoints

### Transactions

| Metode | Endpoint | Beskrivelse |
|--------|----------|------------|
| `GET` | `/transactions/` | Hent alle transaktioner (pagineret) |
| `GET` | `/transactions/{id}` | Hent specifik transaktion |
| `POST` | `/transactions/upload` | Upload CSV med transaktioner |
| `POST` | `/transactions/` | Opret ny transaktion |
| `PUT` | `/transactions/{id}` | Opdater transaktion |
| `DELETE` | `/transactions/{id}` | Slet transaktion |

**Query parameters:**
```bash
GET /transactions/?limit=20&offset=0&start_date=2025-01-01&end_date=2025-01-31&category_id=5
```

### Categories

| Metode | Endpoint | Beskrivelse |
|--------|----------|------------|
| `GET` | `/categories/` | Hent alle kategorier |
| `POST` | `/categories/` | Opret ny kategori |
| `DELETE` | `/categories/{id}` | Slet kategori |

### Budgets

| Metode | Endpoint | Beskrivelse |
|--------|----------|------------|
| `GET` | `/budgets/` | Hent alle budgetter |
| `POST` | `/budgets/` | Opret nyt budget |

### Dashboard

| Metode | Endpoint | Beskrivelse |
|--------|----------|------------|
| `GET` | `/dashboard/summary` | Økonomi oversigt |
| `GET` | `/dashboard/chart-data` | Data til grafer |

---

## 📦 Repository Pattern

### Hvorfor Repository Pattern?

Repository pattern abstrahere fra databaselaget, hvilket gør det:
- ✅ **Testbart:** Mock repositories i tests
- ✅ **Fleksibelt:** Skifte database uden at ændre routes
- ✅ **Vedligehold:** Centraliseret database logik

### Brug af Repository

I dine routes:

```python
from backend.repository import get_transaction_repository

@router.get("/transactions/")
def list_transactions():
    repo = get_transaction_repository()  # Får MySQL eller ES based on config
    transactions = repo.get_all(limit=100)
    return transactions
```

Repository-funktionen returnerer automatisk den rigtige implementering baseret på `ACTIVE_DB`.

### Implementere ny database

1. **Opret ny klasse i `repository/`:**
   ```python
   # repository/mongodb_repository.py
   from backend.repository.base_repository import ITransactionRepository
   
   class MongoDBTransactionRepository(ITransactionRepository):
       def get_all(self, ...):
           # MongoDB implementation
           pass
   ```

2. **Opdater factory i `repository/__init__.py`:**
   ```python
   elif ACTIVE_DB == DatabaseType.MONGODB.value:
       return MongoDBTransactionRepository()
   ```

3. **Tilføj til `config.py`:**
   ```python
   class DatabaseType(Enum):
       # ...
       MONGODB = "mongodb"
   ```

---

## 📊 Data Modeller

### Transaction
```python
{
    "id": 1,
    "description": "Supermarked køb",
    "amount": -250.50,
    "date": "2025-08-04",
    "type": "expense",  # income | expense
    "category_id": 26,
    "balance_after": 15000.00,
    "currency": "DKK",
    "sender": "KVICKLY",
    "recipient": null,
    "name": "KVICKLY BILKA"
}
```

### Category
```python
{
    "id": 26,
    "name": "Madvarer/Dagligvarer",
    "type": "expense"  # income | expense
}
```

### Budget
```python
{
    "id": 1,
    "category_id": 26,
    "amount": 3000.00,
    "month": "08",
    "year": "2025"
}
```

---

## 🔍 Elasticsearch UI

Kibana kører på: **http://localhost:5601**

### I Kibana kan du:
1. **Browse data:** Management → Index Management → transactions
2. **Køre queries:** Dev Tools → Console
3. **Lave dashboards:** Visualize
4. **Søge data:** Discover

**Eksempel query i Kibana Console:**
```json
GET transactions/_search
{
  "query": {
    "bool": {
      "must": [
        { "term": { "category_id": 26 } },
        { "range": { "date": { "gte": "2025-08-01" } } }
      ]
    }
  },
  "aggs": {
    "total_by_date": {
      "date_histogram": {
        "field": "date",
        "calendar_interval": "day"
      },
      "aggs": {
        "total_amount": { "sum": { "field": "amount" } }
      }
    }
  }
}
```

---

## 🧪 Testing

### Test med cURL

```bash
# Hent alle transaktioner
curl http://localhost:8000/transactions/

# Upload CSV
curl -X POST -F "file=@transactions.csv" http://localhost:8000/transactions/upload

# Opret kategori
curl -X POST http://localhost:8000/categories/ \
  -H "Content-Type: application/json" \
  -d '{"name": "Ny Kategori"}'
```

### Test database switch

1. **Start med MySQL:**
   ```bash
   # I .env: ACTIVE_DB=mysql
   curl http://localhost:8000/transactions/ | jq '.value | length'
   # Output: 67
   ```

2. **Skift til Elasticsearch:**
   ```bash
   # I .env: ACTIVE_DB=elasticsearch
   curl http://localhost:8000/transactions/ | jq '.value | length'
   # Output: 67 (samme data!)
   ```

---

## 🆘 Fejlfinding

### Problem: "Unknown column 'transactions.account_id'"
**Årsag:** SQLAlchemy modellen refererer til kolonner der ikke eksisterer i databasen
**Løsning:** Tjek at `database.py` matche den faktiske MySQL schema

### Problem: Elasticsearch forbindelsestal
**Årsag:** Elasticsearch container kører ikke eller er på forkert port
**Løsning:**
```bash
# Check status
docker ps | grep elasticsearch

# Check forbindelse
curl http://localhost:9200

# Genstart container
docker stop elasticsearch
docker rm elasticsearch
# ... start ny container ...
```

### Problem: "BadRequestError(400, 'media_type_header_exception')"
**Årsag:** Version mismatch mellem ES container og Python client
**Løsning:** Brug Elasticsearch 7.17.0, ikke 8.0.0+

### Problem: "nan can not be used with MySQL"
**Årsag:** Pandas CSV import har NaN værdier
**Løsning:** Allerede håndteret i `routers/transactions.py` med `math.isnan()` checks

---

## 📝 Environment Variabler

```bash
# Primær database URL (MySQL)
DATABASE_URL=mysql+pymysql://root:123456@localhost:3307/finans_tracker?charset=utf8mb4

# Aktiv database type (mysql | elasticsearch | hybrid)
ACTIVE_DB=mysql

# Elasticsearch forbindelse
ELASTICSEARCH_HOST=http://localhost:9200

# Auto-sync til Elasticsearch ved nye transaktioner
SYNC_TO_ELASTICSEARCH=false
```

---

## 📚 Dependencies

**Vigtige packages:**

| Package | Version | Formål |
|---------|---------|--------|
| `fastapi` | 0.100+ | Web framework |
| `uvicorn` | 0.23+ | ASGI server |
| `sqlalchemy` | 2.0+ | ORM |
| `pymysql` | 1.1+ | MySQL driver |
| `elasticsearch` | 8.0+ | ES client |
| `pandas` | 2.0+ | CSV parsing |
| `python-dotenv` | 1.0+ | Environment vars |
| `pydantic` | 2.0+ | Data validation |

---

## 🚀 Production Deployment

### Docker Compose (Anbefalet)

Opret `docker-compose.yml`:

```yaml
version: '3.8'

services:
  mysql:
    image: mysql:latest
    environment:
      MYSQL_ROOT_PASSWORD: ${DB_PASSWORD}
      MYSQL_DATABASE: finans_tracker
    ports:
      - "3307:3306"
    volumes:
      - mysql_data:/var/lib/mysql

  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:7.17.0
    environment:
      discovery.type: single-node
      xpack.security.enabled: "false"
      ES_JAVA_OPTS: "-Xms512m -Xmx512m"
    ports:
      - "9200:9200"
    volumes:
      - es_data:/usr/share/elasticsearch/data

  backend:
    build: .
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: mysql+pymysql://root:${DB_PASSWORD}@mysql:3306/finans_tracker
      ACTIVE_DB: mysql
      ELASTICSEARCH_HOST: http://elasticsearch:9200
    depends_on:
      - mysql
      - elasticsearch

volumes:
  mysql_data:
  es_data:
```

Start med:
```bash
docker-compose up -d
```

---

## 📞 Support

Hvis du støder på problemer:

1. **Check logs:** `python -m uvicorn backend.main:app --reload` (viser errors direkte)
2. **Check database:** Se MySQL Workbench eller Kibana
3. **Check config:** Verificer `.env` indstillinger
4. **Genstart services:** Stop og start Docker containers igen

---

**Last updated:** November 2025  
**Status:** ✅ Fully Functional (MySQL + Elasticsearch)
