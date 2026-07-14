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

**Status update 2026-07-14 (AI-20 cutover):** chat's `transaction_search` now runs on
**ES hybrid search** — `EsSearch` adapter (embeds query via Ollama, falls back to
BM25-only on embed failure) → analytics-service `POST /api/v1/analytics/search/hybrid`
(BM25 + pre-filtered kNN on `description_vector`, client-side RRF). Documents are
embedded by a **separate consumer in analytics-service** (`analytics.embeddings` queue,
own DLQ; decision 2026-07-13-embed-worker-placement) — event-synced, so the ghost-data/
manual-re-ingest problems below are gone on the ES path. ChromaDB code still present
behind `SEARCH_BACKEND` (compose = `es`; k8s still defaults to chroma) until the flag
has baked, then plan step 12 deletes it. The ChromaDB descriptions below are
end-of-life documentation.

See [findings/2026-07-07-architecture-audit.md](../../findings/2026-07-07-architecture-audit.md). Status update 2026-07-12 (code survey for [plans/2026-07-12-ai-service-es-chat.md](../../plans/2026-07-12-ai-service-es-chat.md)): ingest-blocks-event-loop **fixed** (P1-09, `anyio.to_thread`), collection wipe **fixed** (P1-10, model-versioned collection `transactions__<model>`), rules-DB dead **fixed** (P2-06), `OLLAMA_BASE_URL` drift **fixed** (P2-16 partial); compose still sets dead env `LLM_MODEL` (config reads `LLM_ROUTER_MODEL`/`LLM_RESPONDER_MODEL`), responder model `qwen3:8b` still not pulled by ollama-pull (models live on the other dev machine — do not change config). Still open: ghost data / manual full re-ingest (P3-04 → AI-20), decorative+drifted ports, unreachable slot→filter path (M24 → AI-02/AI-21), junk `test_chromadb_sanity*/` + broken `scripts/sanity_check_retrieval.py` (P3-07), unauthenticated categorize endpoints (MEDIUM), committed `services/categorization-service/.env` (MEDIUM).
