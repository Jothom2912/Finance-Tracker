# Categorization Service — Phase 1 Retrospective

**Date:** 2026-04-23
**Scope:** Extraction of categorization pipeline from monolith to dedicated microservice

## Problem

The monolith owned the entire categorization domain: taxonomy (categories,
subcategories, merchants), the rule engine (keyword matching), and the
categorization pipeline (rules, ML, LLM fallback). This created three problems:

1. **Coupling:** Changing a keyword rule required deploying the entire monolith,
   including unrelated banking, budget, and account code.
2. **Scaling:** The rule engine is CPU-cheap, but future ML/LLM tiers are
   expensive. They need independent scaling, which is impossible inside a monolith.
3. **Ownership ambiguity:** Categories were half-owned by transaction-service
   (CRUD + events) and half by the monolith (subcategories, merchants, rules,
   pipeline). No single service had complete authority over the categorization
   domain.

## Alternatives Considered

### Where should categorization live?

| Option | Verdict | Reasoning |
|--------|---------|-----------|
| In transaction-service (rule engine as part of transaction ingest) | Rejected | Splits the categorization pipeline: rule engine in tx-service, ML/LLM in a future ai-service. The orchestrator would need to span two services. |
| Dedicated categorization-service | **Chosen** | Passes all three tests: cohesion (taxonomy + rules + engine change together), data ownership (categories are categorization's vocabulary, not a standalone CRUD table), and who-asks-what (categorization is the primary consumer of category data). |
| Separate category-service + categorization-service | Rejected | Category-service would be an anemic CRUD service with no business rules — just a table with an HTTP wrapper. The network overhead is not justified. |

### Sync vs async categorization

| Option | Verdict | Reasoning |
|--------|---------|-----------|
| Pure async (event-driven only) | Rejected | 2-3 second window where transactions are uncategorized in the UI feels like a bug to users, even though it is technically eventual consistency. |
| Pure sync (HTTP call on every transaction) | Rejected | Makes transaction creation dependent on categorization-service availability. Downtime blocks all transaction creation. |
| Hybrid: sync tier 1 + async tier 2/3 | **Chosen** | Rule engine runs in <1ms — fast enough for sync. 70-80% of transactions get instant categorization. The remaining 20-30% get async enrichment via the event pipeline. Cat-service downtime degrades gracefully (500ms timeout, fallback to uncategorized, async catches up later). |

### Primary keys: Integer vs UUID

| Option | Verdict | Reasoning |
|--------|---------|-----------|
| UUID everywhere | Rejected | Every existing service uses Integer. Category IDs 1-10 are pinned across services. UUID would break cross-service compatibility and require an ID mapping layer during migration. |
| Integer (consistent with codebase) | **Chosen** | Eliminates mapping complexity. Subcategory IDs preserved from monolith MySQL. Zero data migration needed on transaction-service side. Trade-off: harder to merge data from multiple sources if multi-tenancy is introduced. Not relevant for a single-tenant app. |

### Shadow mode vs simple overwrite

| Option | Verdict | Reasoning |
|--------|---------|-----------|
| Full shadow mode (parallel run, comparison table, exit criteria) | Rejected | Infrastructure cost (new table, migration, comparison logic, dashboard queries, flip procedure) is disproportionate to the risk. Rule engine is 1:1 ported with 14 unit tests covering keyword matching, sign overrides, and Danish normalization. Miscategorization cost is low (user sees wrong category label, fixable with a migration). |
| Simple overwrite + stdout divergence logging | **Chosen** | Cat-service always overwrites transaction's denormalized categorization. Divergence from monolith's result (during dual-run) logged to stdout. Matches the project's risk profile: under development, single user, low cost of error. |

## What Was Built

### Categorization-service (new)

- Hexagonal architecture: domain, application, adapters (inbound HTTP + outbound Postgres/MQ)
- 7 Postgres tables: categories, subcategories, merchants, categorization_rules,
  categorization_results, outbox_events, processed_events
- Rule engine (1:1 port from monolith): keyword matching with longest-match-first,
  sign-dependent overrides, Danish character normalization
- Categorization pipeline orchestrator: rules -> ML (future) -> LLM (future) -> fallback
- Sync HTTP endpoint: `POST /api/v1/categorize/` for tier 1
- Async consumer: `transaction.created` -> full pipeline -> `transaction.categorized`
- Category CRUD API: `POST/GET/PUT/DELETE /api/v1/categories/`
- Outbox publisher worker for `transaction.categorized` and `category.*` events
- RuleEngineProvider with TTL-based reload (60s) and startup warmup
- Seed data from taxonomy.py with preserved IDs

### Transaction-service (modified)

- `CategorizationClient`: async HTTP client with 500ms timeout + graceful fallback
- `TransactionService.create_transaction`: sync categorize before persist, HTTP call
  outside DB transaction to avoid holding connections
- `TransactionService.bulk_import`: batch categorize for uncategorized items
- `TransactionCategorizedConsumer`: always-overwrite + divergence logging, inbox pattern
- Migration 007: processed_events (inbox) table

### Shared contracts (modified)

- `TransactionCategorizedEvent`: new event type for categorization results

### Infrastructure

- docker-compose: postgres-categorization (port 5435), categorization-service (port 8005),
  categorization-outbox-worker, transaction-categorized-consumer
- Root Makefile: all targets include categorization-service

## Key Bugs Found and Fixed

### Atomicity bug in consumer (critical)

**Found during:** Pre-wiring code review (6-question checklist).

**Problem:** Consumer wrote to three tables in three separate DB sessions:
inbox check (session 1), result + outbox (session 2), inbox record (session 3).
A crash between session 2 commit and session 3 commit would leave the inbox
unwritten, causing duplicate processing on restart.

**Fix:** All three writes (dedup check, categorization result, outbox event,
inbox record) happen in a single `async with session_factory() as session`
with one `session.commit()`. IntegrityError on the inbox UNIQUE constraint
is caught as a benign race condition (two consumers, one wins).

**Lesson:** "I implemented inbox pattern" is not the same as "inbox pattern works."
The atomicity guarantee only holds if all writes share the same DB transaction.

### Inbox cleanup window (medium)

**Problem:** `CLEANUP_DAYS = 7`. DLQ messages could sit for 8+ days before
manual replay, at which point the inbox row was already deleted. Replay
would process the message again (duplicate).

**Fix:** `CLEANUP_DAYS = 30` + safety guard that aborts if cleanup would
delete >90% of the table (catches container clock skew).

### Cold-start timeout (medium)

**Problem:** 500ms timeout for sync categorization HTTP call. First request
after service startup triggers lazy initialization (DB pool + rule engine
load), which can take 1-2 seconds. Every first request would timeout and
fall back to uncategorized.

**Fix:** `RuleEngineProvider` with `@app.on_event("startup")` warmup.
DB pool and rule engine preloaded before first request. 500ms timeout is
now realistic for a warm service.

## Trade-offs

| What we gain | What we give up |
|-------------|-----------------|
| Independent deployment of categorization logic | Network hop for sync categorization (500ms budget) |
| Future ML/LLM scaling independent of transactions | Operational complexity (new service, new DB, new workers) |
| Rules as data (auditable, runtime-changeable) | Rules were simpler as code (taxonomy.py, change with a PR) |
| Atomic audit trail in categorization_results | Storage cost (one row per categorization attempt) |
| Graceful degradation on cat-service downtime | Eventual consistency window for uncategorized transactions |

## Deferred as Technical Debt

### 1. Category ownership transfer

**Status:** Cat-service has its own categories table with CRUD + events, but
transaction-service still owns the authoritative copy. Frontend and budget-service
still point to transaction-service for categories.

**When to address:** Before Phase 2 (ML/LLM integration), because ML needs
access to the full taxonomy, which should live in the authoritative service.

**Effort:** 1-2 days. Involves frontend URL changes, budget-service consumer
rewiring, and removing category CRUD from transaction-service.

### 2. ML and LLM categorizer adapters

**Status:** Ports defined (`IMlCategorizer`, `ILlmCategorizer`), pipeline
orchestrator supports them, but no adapters implemented.

**When to address:** Phase 2 planning. The pipeline is ready; only the
adapter implementations and model training/hosting are needed.

### 3. User-specific rules

**Status:** `categorization_rules.user_id` column exists, rule engine query
supports `WHERE user_id = :uid OR user_id IS NULL`, but no API or UI for
creating user rules.

**When to address:** After basic categorization is stable in production.
The schema supports it; the feature is a UI + API addition.

### 4. Monolith categorization removal

**Status:** Monolith's `BankingService` still runs its local rule engine
before sending transactions to transaction-service. Cat-service's async
pipeline overwrites the result. Both produce the same output (1:1 port),
so the dual-run is a no-op in practice.

**When to address:** After category ownership transfer. Remove
`get_categorization_service` from monolith's dependencies.py and strip
categorization fields from the banking bulk DTO.

## What I Would Do Differently

1. **Start with the schema design document.** I wrote SCHEMA.md after building
   the skeleton but before writing migrations. The 30 minutes of upfront design
   caught the ID preservation strategy and delete policy before they became
   migration bugs. I should have written it even earlier — before any code.

2. **The atomicity bug was preventable.** If I had written the consumer's
   integration test before the consumer itself (test-first), I would have
   discovered the three-session problem immediately. Instead, I wrote the
   consumer, passed unit tests (which don't test DB transactions), and the
   bug survived until the pre-wiring review. Test-first for anything involving
   DB transactions.

3. **Shadow mode was over-engineering.** I spent time planning infrastructure
   (comparison tables, divergence queries, exit criteria) that wasn't justified
   by the project's risk profile. The simpler approach (always overwrite + log
   divergence) gives 90% of the observability at 10% of the cost. Match the
   solution to the problem, not to the pattern catalogue.
