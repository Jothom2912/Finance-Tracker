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

## Current Architecture

All new development follows the hexagonal bounded context pattern. The shared `repositories/` layer remains as infrastructure for multi-database support, with factory functions in `__init__.py` selecting the right implementation based on `ACTIVE_DB`, `TRANSACTIONS_DB`, `ANALYTICS_DB`, and `USER_DB` environment variables.
