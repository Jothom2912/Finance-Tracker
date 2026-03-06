# Migration History: Repository Layer

## Previous Migrations

### 1. `repository/` to `repositories/` (completed)

The original single-file `repository/` folder was split into database-specific subfolders:

```
# Before
repository/
├── base_repository.py
├── mysql_repository.py
└── elasticsearch_repository.py

# After
repositories/
├── base.py
├── mysql/          # One file per entity
├── elasticsearch/  # One file per entity
├── neo4j/          # One file per entity
└── __init__.py     # Factory functions
```

Import changes: `backend.repository` became `backend.repositories`, and `base_repository` became `base`.

### 2. Legacy services/routes to hexagonal architecture (completed)

The backend migrated from a flat `routes/ → services/ → repositories/` structure to hexagonal architecture with bounded contexts:

```
# Before (legacy)
routes/transactions.py → services/transaction_service.py → repositories/

# After (hexagonal)
transaction/
├── adapters/inbound/rest_api.py      # Inbound adapter
├── adapters/outbound/mysql_repository.py  # Outbound adapter
├── application/
│   ├── ports/inbound.py              # Service interface
│   ├── ports/outbound.py             # Repository interface
│   └── service.py                    # Application service
└── domain/entities.py                # Domain entities
```

The shared `repositories/` folder is still used as infrastructure for the multi-database factory that the hexagonal outbound adapters delegate to.

### 3. Legacy GraphQL to hexagonal read gateway (completed)

The standalone `backend/graphql/` directory (which accessed `SessionLocal` directly, bypassing service layers) was removed and replaced by `backend/analytics/adapters/inbound/graphql_api.py` -- a proper hexagonal inbound adapter that injects services via FastAPI DI and serves as a cross-domain read gateway.

### 4. Transaction and Analytics domains fully migrated (completed)

The Transaction and Analytics bounded contexts no longer import from the shared `repositories/` layer. Their outbound adapters contain self-contained database queries:

- **Transaction domain** uses `transaction/adapters/outbound/mysql_repository.py` with `flush()` instead of `commit()`/`rollback()`. The `TransactionService` wraps writes in an `IUnitOfWork` that controls the transaction boundary.
- **Analytics domain** uses direct SQLAlchemy/Elasticsearch/Neo4j queries in its own adapters, without delegating to the shared repository factory.
- **Auth module** uses `IAccountResolver` port instead of importing from `backend.repositories`.

Architecture fitness tests in `tests/architecture/test_import_boundaries.py` enforce these boundaries at CI time.

## Current Architecture

All new development follows the hexagonal bounded context pattern. The Transaction and Analytics domains have fully migrated to domain-specific adapters. Other domains still delegate to the shared `repositories/` layer, which provides multi-database support via factory functions in `__init__.py` based on `ACTIVE_DB`, `TRANSACTIONS_DB`, `ANALYTICS_DB`, and `USER_DB` environment variables.
