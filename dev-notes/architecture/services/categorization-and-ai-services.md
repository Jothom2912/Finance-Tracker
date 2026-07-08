---
title: categorization-service + ai-service
updated: 2026-07-07
source: architecture audit 2026-07-07
---

# categorization-service (8005) & ai-service (8007)

## categorization-service — multi-tier pipeline & taxonomy owner (ADR-003)

- **Inbound**: `categorize_api.py` (`POST /api/v1/categorize/` + `/batch`, sync tier-1, called by transaction-service — **no auth on these endpoints**), `category_api.py` (taxonomy CRUD, JWT, sole taxonomy writer, full-state `category.*`/`subcategory.*` events via outbox).
- **Application**: `categorization_service.py` — tier orchestrator (rules → ML → LLM → fallback), but ML/LLM ports are `Optional` and **nothing implements them**; in practice rules → fallback. `category_service.py` — taxonomy CRUD with "Anden" fallback delete-protection.
- **Rule engine**: in-memory longest-match keyword matching with Danish transliteration. ⚠ Keywords come from hardcoded `SEED_MERCHANT_MAPPINGS` in `app/domain/taxonomy.py` — the seeded `categorization_rules` DB table + `PostgresRuleRepository` are **dead**; editing rules in DB has zero effect. `rule_engine_provider.py` has 60s TTL reload (of the name→id lookup only).
- **Workers**: `transaction_consumer.py` (consumes `transaction.created`; **re-implements** the tier logic inline, builds its own engine once at startup — no TTL, bypasses `CategorizationService`), `outbox_publisher.py` (standard poll/SKIP LOCKED copy).
- Result path: `categorization_results` + outbox `TransactionCategorizedEvent` + inbox row in one transaction.

## ai-service — streaming RAG chat

- **Endpoints**: `POST /api/v1/chat/stream` (SSE), `POST /api/v1/ingest`, `/health`. JWT + `X-Account-ID` (forwarded unverified — relies on downstream validation).
- **Pipeline** (`application/pipeline.py`): router (qwen3:4b, constrained JSON sampling, 4 intents) → dispatcher (gateway dashboard / transaction list / budget summary / ChromaDB hybrid search with `user_id` tenant filter) → responder (qwen3:8b, thinking discarded, sync Ollama stream bridged via anyio channel). Typed discriminated-union SSE events with latencies — well designed.
- **Ingest**: manual full re-fetch + re-embed of a user's whole history (batch 50) into a **single shared** `transactions` ChromaDB collection (embedded `PersistentClient` → single-replica only). No event-driven sync; deletes never removed (ghost data). Dimension mismatch → **drops the whole collection for all users**.
- **Ports** (`application/ports/`) are decorative — pipeline types against concrete adapters, port signatures drifted from reality.
- Untracked junk: `test_chromadb_sanity*/` (binary vector DBs of personal data), `scripts/sanity_check_retrieval.py` (broken import of deleted `app.application.retriever`).

## Data flows

- **Categorization**: tx-service sync HTTP call at create (tier 1) → `transaction.created` event → consumer rule-engine → result + outbox → `transaction.categorized` → tx-service consumer updates denormalized fields.
- **Chat**: SSE `intent_resolved` → `data_ready` → `prose_chunk`* → `done` (timings). ChromaDB search embeds query with bge-m3, filters on `user_id` + `year_month`.

## Open problems

See [findings/2026-07-07-architecture-audit.md](../../findings/2026-07-07-architecture-audit.md). Headliners: ingest blocks the event loop freezing all SSE streams (CRITICAL), rules DB dead vs hardcoded seed (HIGH), consumer duplicates+bypasses orchestrator (HIGH), compose model/config drift breaks responder on fresh host — responder model `qwen3:8b` never pulled, `OLLAMA_BASE_URL` points at host not compose ollama (HIGH), one user's ingest can wipe all users' vectors (HIGH), unauthenticated categorize endpoints (MEDIUM), `JWT_SECRET=""` fail-open default (MEDIUM), committed `services/categorization-service/.env` (MEDIUM).
