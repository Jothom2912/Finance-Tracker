---
title: categorization-service + ai-service
updated: 2026-07-17
source: architecture audit 2026-07-07; F1-02/03 update 2026-07-17
---

# categorization-service (8005) & ai-service (8007)

## categorization-service — multi-tier pipeline & taxonomy owner (ADR-003)

- **Inbound**: `categorize_api.py` (`POST /api/v1/categorize/` + `/batch`, sync tier-1, called by transaction-service — **no auth on these endpoints**, `user_id` in body), `category_api.py` (taxonomy CRUD, JWT, sole taxonomy writer, full-state `category.*`/`subcategory.*` events via outbox), `rules_api.py` *(F1-02, 2026-07-17)* — `/api/v1/rules` user-scoped rule CRUD (JWT via shared auth; KEYWORD only, priority default 50 clamped to [20,90]).
- **Application**: `categorization_service.py` — tier orchestrator (rules → ML → LLM → fallback), but ML/LLM ports are `Optional` and **nothing implements them**; in practice rules → fallback. `category_service.py` — taxonomy CRUD with "Anden" fallback delete-protection. `rule_service.py` *(F1-02)* — user rule CRUD, invalidates the per-user engine overlay (API process only).
- **Rule engine** *(rewired 2026-07-17, F1-02)*: `TieredRuleEngine` — DB-backed rules via `PostgresRuleRepository` (P2-06 wired it; seed rules live in `categorization_rules` with `user_id NULL`, priority 100). Priority ladder **10 = learned / 50 = user / 100 = seed**; tiers matched in priority order, longest-match within a tier — user intent beats seed keyword length. `rule_engine_provider.py`: cached global engine + per-user TTL overlay (60s); `get(user_id)`. Danish transliteration/normalization unchanged.
- **Workers**: `transaction_consumer.py` (consumes `transaction.created`; uses `CategorizationService` + shared provider since P2-06 — user rules apply on the event path, picked up within the 60s TTL), `category_corrected_consumer.py` *(F1-03, 2026-07-17)* — consumes `transaction.category_corrected` (queue `categorization.category_corrected`, own DLQ + inbox), upserts a learned user rule (`MERCHANT`, priority 10, normalized description; partial unique index from migration 007). Parent-only corrections (no subcategory) are skipped. `outbox_publisher.py` (standard poll/SKIP LOCKED copy).
- Result path: `categorization_results` + outbox `TransactionCategorizedEvent` + inbox row in one transaction.
- **Feedback loop** *(F1-03)*: manual category change in tx-service (`update_transaction`, same condition that sets `tier="manual"`) → outbox `TransactionCategoryCorrectedEvent` → corrected-consumer writes a learned rule → next import of that merchant auto-categorizes correctly. Consumer writes *rules only*, never transactions — no event cycle. See [decisions/2026-07-17-learned-corrections-as-rules.md](../../decisions/2026-07-17-learned-corrections-as-rules.md). E2e-verified live 2026-07-17 (correction → rule ~2s; re-import lands in corrected category).

## ai-service — streaming RAG chat

- **Endpoints**: `POST /api/v1/chat/stream` (SSE), `/health`. JWT + `X-Account-ID` (forwarded unverified — relies on downstream validation). (`POST /api/v1/ingest` deleted 2026-07-17 with ChromaDB — the ES index is event-synced, nothing to trigger.)
- **Pipeline** (`application/pipeline.py`): router (qwen3:4b, constrained JSON sampling, 4 intents) → dispatcher (analytics-service ES aggregations / budget summary / ES hybrid search with `user_id` tenant filter) → responder (qwen3:8b, thinking discarded, sync Ollama stream bridged via anyio channel). Typed discriminated-union SSE events with latencies — well designed.
- **Ports** (`application/ports/`): real since 2026-07-12 — `@runtime_checkable`, dispatcher typed against them, conformance + signature-drift tests in `test_architecture.py`.
- ~~Ingest / ChromaDB~~ **deleted 2026-07-17** (plan 2026-07-12 step 12 after 3-day bake): `chromadb_search/vectorstore/ingest_service/ingest_api/transaction_client` gone, `get_ollama_client` moved to `ollama_client.py`, frontend "Opdater vidensbase" button removed. Semantic search = ES hybrid only.

## Data flows

- **Categorization**: tx-service sync HTTP call at create (tier 1) → `transaction.created` event → consumer rule-engine → result + outbox → `transaction.categorized` → tx-service consumer updates denormalized fields.
- **Chat**: SSE `intent_resolved` → `data_ready` → `prose_chunk`* → `done` (timings). Hybrid search embeds the query with bge-m3 (httpx → Ollama), sends text + vector to analytics-service; degrades to BM25-only if embedding fails.

## Open problems

**Status update 2026-07-14 (AI-20 cutover):** chat's `transaction_search` now runs on
**ES hybrid search** — `EsSearch` adapter (embeds query via Ollama, falls back to
BM25-only on embed failure) → analytics-service `POST /api/v1/analytics/search/hybrid`
(BM25 + pre-filtered kNN on `description_vector`, client-side RRF). Documents are
embedded by a **separate consumer in analytics-service** (`analytics.embeddings` queue,
own DLQ; decision 2026-07-13-embed-worker-placement) — event-synced, so the ghost-data/
manual-re-ingest problems below are gone. **2026-07-17: ChromaDB code deleted entirely**
(plan step 12; `SEARCH_BACKEND` flag removed, ES is the only backend, compose volume +
k8s PVC removed). Historic ChromaDB mentions below are end-of-life documentation.

See [findings/2026-07-07-architecture-audit.md](../../findings/2026-07-07-architecture-audit.md). Status update 2026-07-12 (code survey for [plans/2026-07-12-ai-service-es-chat.md](../../plans/2026-07-12-ai-service-es-chat.md)): ingest-blocks-event-loop **fixed** (P1-09, `anyio.to_thread`), collection wipe **fixed** (P1-10, model-versioned collection `transactions__<model>`), rules-DB dead **fixed** (P2-06), `OLLAMA_BASE_URL` drift **fixed** (P2-16 partial); compose still sets dead env `LLM_MODEL` (config reads `LLM_ROUTER_MODEL`/`LLM_RESPONDER_MODEL`), responder model `qwen3:8b` still not pulled by ollama-pull (models live on the other dev machine — do not change config). Still open: ghost data / manual full re-ingest (P3-04 → AI-20), decorative+drifted ports, unreachable slot→filter path (M24 → AI-02/AI-21), junk `test_chromadb_sanity*/` + broken `scripts/sanity_check_retrieval.py` (P3-07), unauthenticated categorize endpoints (MEDIUM), committed `services/categorization-service/.env` (MEDIUM).
