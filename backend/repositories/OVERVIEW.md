# Repository Pattern -- How It Works

## What Is the Repository Pattern?

The repository pattern abstracts the data access layer. Instead of coding directly against MySQL, Elasticsearch, or Neo4j, we define repository interfaces and let factory functions select the right implementation based on configuration.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│               Inbound Adapters (REST / GraphQL)         │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│              Application Services                        │
│    (injected via dependencies.py using Depends())       │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│              Outbound Ports (ABC interfaces)             │
│    (defined in each domain's application/ports/)        │
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

## Data Flow

### 1. Request arrives at inbound adapter

```python
@router.post("/", status_code=201)
def create_transaction(
    transaction: TransactionCreate,
    service: TransactionService = Depends(get_transaction_service),
    account_id: int = Depends(get_account_id_from_headers),
):
    return service.create_transaction(transaction, account_id)
```

### 2. DI wiring selects repository

```python
def get_transaction_service(db: Session = Depends(get_db)) -> TransactionService:
    return TransactionService(
        transaction_repo=get_transaction_repository(db),
        category_repo=get_category_repository(db),
    )
```

### 3. Factory selects implementation based on config

```python
def get_transaction_repository(db: Session = None):
    if TRANSACTIONS_DB == "mysql":
        return MySQLTransactionRepository(db)
    elif TRANSACTIONS_DB == "elasticsearch":
        return ElasticsearchTransactionRepository()
    elif TRANSACTIONS_DB == "neo4j":
        return Neo4jTransactionRepository()
```

### 4. Repository executes database-specific query

- **MySQL**: SQL via SQLAlchemy ORM
- **Elasticsearch**: Query DSL (JSON)
- **Neo4j**: Cypher queries

All repositories return the same data format, so the service layer is database-agnostic.

## Database Selection

Switch databases by changing environment variables -- no code changes needed:

```bash
# Use MySQL for everything (default)
ACTIVE_DB=mysql

# Use Elasticsearch for analytics only
ANALYTICS_DB=elasticsearch

# Use Neo4j for analytics
ANALYTICS_DB=neo4j
```

## Design Principles

1. **Dependency inversion** -- services depend on interfaces (ports), not concrete repositories
2. **Single responsibility** -- each repository handles one entity type
3. **Open/closed** -- add new databases without modifying existing code
4. **Constructor injection** -- repositories are injected into services via FastAPI `Depends()`

## See Also

- `README.md` -- directory structure and support matrix
- `base.py` -- abstract interface definitions
- `backend/dependencies.py` -- DI wiring for all services
