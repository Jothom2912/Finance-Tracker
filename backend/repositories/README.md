# Repository Layer -- Multi-Database Infrastructure

This folder contains the shared repository infrastructure that provides multi-database support across MySQL, Elasticsearch, and Neo4j.

## Role in Hexagonal Architecture

In the current hexagonal architecture, each bounded context (e.g. `transaction/`, `budget/`) has its own outbound adapters that implement repository interfaces defined in `application/ports/outbound.py`. This shared `repositories/` layer provides the underlying database-specific implementations that those outbound adapters delegate to.

```
Bounded Context (e.g. transaction/)
├── application/ports/outbound.py    # Port interface (TransactionRepository ABC)
├── adapters/outbound/
│   └── mysql_repository.py          # Outbound adapter (implements port, uses shared repo)
│
Shared Infrastructure (repositories/)
├── base.py                          # Abstract interfaces (legacy, still used by factory)
├── __init__.py                      # Factory functions for database selection
├── mysql/                           # MySQL implementations
├── elasticsearch/                   # Elasticsearch implementations
└── neo4j/                           # Neo4j implementations
```

## Directory Structure

```
repositories/
├── __init__.py                    # Factory functions (select repository by ACTIVE_DB)
├── base.py                        # Abstract interfaces (ABC)
├── mysql/
│   ├── transaction_repository.py
│   ├── category_repository.py
│   ├── account_repository.py
│   ├── account_group_repository.py
│   ├── user_repository.py
│   ├── budget_repository.py
│   ├── goal_repository.py
│   └── planned_transaction_repository.py
├── elasticsearch/
│   ├── transaction_repository.py
│   ├── category_repository.py
│   ├── account_repository.py
│   ├── budget_repository.py
│   ├── goal_repository.py
│   └── user_repository.py
└── neo4j/
    ├── transaction_repository.py
    ├── category_repository.py
    ├── account_repository.py
    ├── budget_repository.py
    ├── goal_repository.py
    └── user_repository.py
```

## Database Selection

The factory in `__init__.py` selects the right implementation based on environment variables:

| Variable | Scope | Default |
|----------|-------|---------|
| `ACTIVE_DB` | Global fallback | `mysql` |
| `TRANSACTIONS_DB` | Transaction domain | `mysql` |
| `ANALYTICS_DB` | Analytics domain | `ACTIVE_DB` |
| `USER_DB` | User domain | `mysql` |

```bash
# Switch to Elasticsearch for analytics
ANALYTICS_DB=elasticsearch

# Switch everything to Neo4j
ACTIVE_DB=neo4j
```

## Repository Support Matrix

| Repository | MySQL | Elasticsearch | Neo4j |
|------------|-------|---------------|-------|
| Transaction | Yes | Yes | Yes |
| Category | Yes | Yes | Yes |
| Account | Yes | Yes | Yes |
| User | Yes | Yes | Yes |
| Budget | Yes | Yes | Yes |
| Goal | Yes | Yes | Yes |

MySQL has the most complete implementations. Elasticsearch and Neo4j implementations cover the same interfaces but may have limitations for certain query patterns.

## Usage in Hexagonal Domains

The bounded context outbound adapters in `<context>/adapters/outbound/` use these repositories. The DI wiring in `dependencies.py` selects the right implementation:

```python
from backend.repositories import get_transaction_repository

def get_transaction_service(db: Session = Depends(get_db)) -> TransactionService:
    return TransactionService(
        transaction_repo=get_transaction_repository(db),
        category_repo=get_category_repository(db),
    )
```

Services never access repositories directly from routes. The flow is:

```
Inbound Adapter → Service → Outbound Port → Repository Adapter → Database
```
