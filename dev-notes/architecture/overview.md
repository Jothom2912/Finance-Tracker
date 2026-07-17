---
title: System architecture overview
updated: 2026-07-07
source: architecture audit 2026-07-07 (8 parallel deep-dives, all services + infra)
---

# System architecture overview

Personal finance tracker as **event-driven microservices**. 10 FastAPI services + React SPA, PostgreSQL database-per-service (8 instances), single RabbitMQ topic exchange `finans_tracker.events`, transactional outbox everywhere, saga orchestration for bank sync, Ollama+ChromaDB AI chat. Legacy Django/MySQL monolith fully retired (0 tracked files remain).

## Service map

| Service | Port | Role | Stack notes |
|---|---|---|---|
| user-service | 8001 | Auth, JWT issuer (sole) | async; cleanest hexagonal exemplar |
| transaction-service | 8002 | Tx CRUD, CSV import, saga participant, taxonomy read-copies | async; 4 workers |
| budget-service | 8003 | Budgets + monthly budgets, month-close → surplus event | async; two parallel budget domains |
| account-service | 8004 | Accounts, groups, default-account-on-signup | **sync** stack, monolith residue |
| categorization-service | 8005 | Rule-tier categorization, **taxonomy owner** (ADR-003) | ML/LLM tiers scaffolded, unwired |
| goal-service | 8006 | Savings goals, surplus allocation | async; best consumer pattern (DLQ+retry) |
| ai-service | 8007 | SSE chat (router→dispatcher→responder), ChromaDB RAG | embedded ChromaDB → single replica |
| banking-service | 8009 | PSD2 via Enable Banking, saga participant | sync EB client in async contexts |
| gateway-service | 8010 | Read BFF: REST dashboard + GraphQL + saga proxy | sync httpx, sequential "fan-out" |
| saga-service | 8011 | Generic saga orchestrator (bank_sync) | 4 processes; unauthenticated status API |

Frontend: React/Vite SPA calling **8 services directly** (gateway only for GraphQL reads + saga status) — TanStack Query, no Redux.

## Core patterns (they work — keep them)

Per-pattern deep-dives with canonical implementations and gotchas live in [../patterns/](../patterns/README.md).

- **[Transactional outbox](../patterns/transactional-outbox.md)**: domain write + `outbox_events` row in one transaction; per-service worker polls with `FOR UPDATE SKIP LOCKED`, publishes to the topic exchange, exponential backoff. At-least-once.
- **[Inbox idempotency](../patterns/idempotent-consumers.md)**: consumers dedupe via `processed_events` tables (or deterministic `source_key` + unique constraints in goal-service).
- **[CQRS-lite](../patterns/cqrs-es-read-store.md)**: REST writes on domain services, GraphQL/REST reads via gateway BFF over the ES read-store (ADR-0004).
- **[Taxonomy read-copies](../patterns/read-copies-and-denormalization.md)** (ADR-003): categorization-service owns categories; transaction-service maintains local copies via `category.*`/`subcategory.*` full-state events.
- **[Saga orchestration](../patterns/saga-orchestration.md)**: saga-service state machine + command/reply over the topic exchange, compensation on failure, outboxed commands.

## Data flows (as-built)

1. **Register** → user-service (UoW: user + outbox) → `user.created` → account-service consumer → default account (+ `account.created` → banking projection).
2. **Create transaction** → sync tier-1 categorization HTTP (500ms budget, graceful degrade) → insert + outbox → `transaction.created` → categorization consumer → `transaction.categorized` → tx-service consumer updates denormalized fields.
3. **Bank sync** → connect/callback (OAuth, single-use state) → sync request → `saga.bank_sync.start` → fetch (EB, paginated) → reply *with all transactions inline* → context → `bulk_import` → `mark_sync_complete`; frontend polls saga status. Compensation: `rollback_import` (hard delete).
4. **Month close** → budget-service computes surplus (HTTP spent-fetch) → `budget.month_closed` → goal-service allocates to default goal.
5. **Dashboard read** → gateway → ownership check (HTTP) → transaction history + categories (HTTP, currently unbounded & sequential) → in-memory aggregation → REST/GraphQL.
6. **AI chat** → SSE: router (qwen3:4b intent) → dispatcher (gateway/tx/budget HTTP or ChromaDB) → responder (qwen3:8b) streaming Danish prose.

## The five systemic problems (cross-cutting themes)

1. **Copy-paste infrastructure instead of shared libs**: outbox worker ×8, rabbitmq publisher ×7, `app/auth.py` ×9 (plus dead `shared/auth`), alembic env ×7, Dockerfile template ×7, `budget_period.py` ×3 — all already drifting. `shared/contracts` proves the uv path-dependency mechanism works; use it.
2. **Fail-open trust boundaries**: empty-string JWT secret defaults (gateway, ai), fail-open cross-service validation (budget's transaction/category ports), unauthenticated endpoints (saga status, account-groups, categorize), IDOR (monthly-budgets, bank disconnect/list), budget-service minting arbitrary user JWTs, one shared HS256 secret platform-wide.
3. **Unbounded reads on the hot path**: gateway fetches full transaction history per dashboard render (sequentially, twice for month-compare); transaction list endpoints have no LIMIT; broken/no-op response caches (cache key includes object repr) in tx- and budget-service.
4. **At-least-once hygiene gaps**: retries republished to the shared topic exchange (fan-out to all subscribers), `json.loads` outside try → poison-message loops, prefetch=1 + inline sleeps, saga timeout abandons without compensation, no outbox purge/dead-letter caps.
5. **Dead scaffolding that misleads**: categorization rules DB unused (hardcoded seed is live), ML/LLM tiers unreachable, decorative ports in ai-service, 3.5k-line dead frontend Budget module, dead `SyncUnitOfWork`, stub services.

Full findings: [findings/2026-07-07-architecture-audit.md](../findings/2026-07-07-architecture-audit.md). Per-service breakdowns in [services/](services/). Deployment/CI details: [infrastructure.md](infrastructure.md).
