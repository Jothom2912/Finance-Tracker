# Backend Structure (Monolith — Hexagonal + CQRS)

## Overview

The monolith backend uses hexagonal architecture across all domains with a CQRS split:

- **REST** for commands (write operations)
- **GraphQL** for queries (read operations via a cross-domain read gateway)

All routes are versioned under `/api/v1/`. The `/health` and `/` endpoints remain at root.

**Note:** The user, transaction, and category domains have been extracted into standalone microservices (`user-service` on port 8001, `transaction-service` on port 8002). The monolith retains local copies of user and category data via event-driven sync. `user-service` is the source of truth for authentication, and `transaction-service` is the source of truth for transactions and categories. See the root `README.md` for the full microservices architecture.

## Runtime Entry Points

- `backend/main.py` — registers routers, middleware (CORS, request logging, correlation ID), and the GraphQL endpoint.
- `backend/dependencies.py` — wires application services with outbound adapters via FastAPI DI.
- `backend/shared/ports/` — cross-cutting port interfaces (`IAccountResolver`, `IUnitOfWork`).
- `backend/shared/adapters/` — cross-cutting adapter implementations (`MySQLAccountResolver`, `MySQLUnitOfWork`, auth DI wiring).
- `tests/architecture/test_import_boundaries.py` — architecture fitness tests that enforce import boundaries at CI time.

## Active Bounded Contexts (still in monolith)

- `backend/transaction/` — CRUD, CSV import, planned transactions
- `backend/category/` — CRUD + three-level hierarchy (Category / SubCategory / Merchant) + categorization pipeline (rule engine, ML/LLM ports)
- `backend/banking/` — PSD2 bank integration via Enable Banking (OAuth flow, transaction sync, deduplication, auto-categorization)
- `backend/budget/` — legacy per-category budgets
- `backend/monthly_budget/` — aggregate-based monthly budgets with budget lines
- `backend/analytics/` — dashboard overview, GraphQL read gateway
- `backend/account/` — CRUD + account groups
- `backend/goal/` — CRUD
- `backend/user/` — registration/login (delegates to monolith MySQL, but user-service is source of truth)

Each context follows the same layout:

```text
<context>/
├── adapters/
│   ├── inbound/       # REST API (+ GraphQL for analytics)
│   └── outbound/      # Repository implementations, external API clients
├── application/
│   ├── ports/         # Inbound + outbound interfaces (protocols)
│   ├── service.py     # Application service
│   └── dto.py         # Data transfer objects
├── domain/
│   ├── entities.py    # Domain entities (dataclasses)
│   ├── value_objects.py # Value objects and enums
│   └── exceptions.py
├── presentation/      # (banking only) REST API routes
└── __init__.py
```

### Banking context structure

```text
backend/banking/
├── adapters/
│   └── outbound/
│       └── enable_banking_client.py   # JWT-signed HTTP client for Enable Banking API
├── application/
│   ├── ports/
│   │   └── outbound.py               # IBankConnectionRepository, IBankingApiClient
│   └── service.py                    # BankingService (orchestrates OAuth + sync)
└── presentation/
    └── rest_api.py                   # FastAPI routes (/bank/*)
```

### Category context structure (with categorization pipeline)

```text
backend/category/
├── adapters/
│   └── outbound/
│       ├── mysql_repository.py            # Category CRUD
│       ├── mysql_subcategory_repository.py # SubCategory CRUD
│       ├── mysql_merchant_repository.py   # Merchant CRUD
│       └── rule_engine.py                 # Keyword-based categorizer (longest-match-first)
├── application/
│   ├── ports/
│   │   └── outbound.py                   # IRuleEngine, IMlCategorizer, ILlmCategorizer
│   └── categorization_service.py         # Multi-tier orchestrator
└── domain/
    ├── entities.py                       # Category, SubCategory, Merchant
    └── value_objects.py                  # CategorizationTier, CategorizationResult
```

## Event Consumers

The monolith includes three independent RabbitMQ consumers:

| Consumer | Queue | Routing Key | Responsibility |
|----------|-------|-------------|---------------|
| `UserSyncConsumer` | `monolith.user_sync` | `user.created` | Sync user data to MySQL User table |
| `AccountCreationConsumer` | `monolith.account_creation` | `user.created` | Create default account in MySQL |
| `CategorySyncConsumer` | `monolith.category_sync` | `category.*` | Sync categories from transaction-service to MySQL |

All consumers:
- Inherit from `BaseConsumer` with retry (3 attempts), DLQ, and DB-backed idempotency (`processed_events` table with auto-cleanup after 7 days)
- Run independently — failure in one does not affect the other
- Can be scaled independently via `--consumer` argument to `worker.py`

```bash
# Run specific consumer
python -m backend.consumers.worker --consumer user-sync
python -m backend.consumers.worker --consumer account-creation
python -m backend.consumers.worker --consumer category-sync

# Run all consumers
python -m backend.consumers.worker
```

## Cross-Service Architecture Decisions

### No FK constraints to User table

The MySQL `Account.User_idUser` and `AccountGroups_has_User.User_idUser` columns have **no foreign key constraints** referencing the `User` table. This is intentional — in a microservices architecture, the MySQL User table is a local cache synced via events, not the source of truth. Cross-service referential integrity is maintained through eventual consistency, not database constraints.

The ORM relationships on `User.account_groups` and `AccountGroups.users` use explicit `primaryjoin`/`secondaryjoin`/`foreign_keys` parameters to work without FK metadata.

### JWT Cross-Service Compatibility

The monolith creates tokens with both `sub` (standard JWT claim) and legacy `user_id`/`username`/`email` fields. Token validation accepts either format, so tokens from both the monolith and user-service work across all services.

## Router Map

| Path | Domain | Protocol |
|------|--------|----------|
| `/api/v1/transactions/*` | Transaction | REST |
| `/api/v1/planned-transactions/*` | Transaction | REST |
| `/api/v1/categories/*` | Category (local cache) | REST |
| `/api/v1/bank/*` | Banking (PSD2) | REST |
| `/api/v1/budgets/*` (CRUD) | Budget (legacy) | REST |
| `/api/v1/budgets/summary` | Analytics | REST |
| `/api/v1/monthly-budgets/*` (CRUD + copy) | Monthly Budget | REST |
| `/api/v1/monthly-budgets/summary` | Monthly Budget | REST |
| `/api/v1/dashboard/*` | Analytics | REST |
| `/api/v1/accounts/*` | Account | REST |
| `/api/v1/account-groups/*` | Account | REST |
| `/api/v1/goals/*` | Goal | REST |
| `/api/v1/users/*` | User | REST |
| `/api/v1/graphql` | Analytics (read gateway) | GraphQL |

## Middleware Stack

1. **CORS** — configured via `CORS_ORIGINS` env var.
2. **Request Logging** — logs method, path, status, duration_ms, and correlation_id.
3. **Correlation ID** — generates UUID per request (or forwards `X-Correlation-ID` header). Returned in `X-Correlation-ID` response header.

## Database Role Configuration

Settings in `backend/config.py`:

- `ACTIVE_DB` — global fallback
- `TRANSACTIONS_DB` — transaction domain
- `ANALYTICS_DB` — analytics domain (supports MySQL, Elasticsearch, Neo4j)
- `USER_DB` — user domain

## SQLAlchemy Models

| Model | Table | Description |
|-------|-------|-------------|
| `Category` | `Category` | Top-level expense/income categories with `display_order` |
| `SubCategory` | `subcategory` | Second-level categories linked to Category |
| `Merchant` | `merchant` | Learned merchant entities linked to SubCategory |
| `Transaction` | `Transaction` | Financial transactions with `subcategory_id`, `merchant_id`, `categorization_tier` |
| `BankConnection` | `bank_connection` | PSD2 bank connections with `session_id`, `iban`, `bank_name`, `last_synced_at` |
| `Account` | `Account` | User accounts |
| `User` | `User` | Local user cache (synced via events) |
