---
title: AI-service on the ES read-store — structured intents, hybrid search, slot filters, cleanup
date: 2026-07-12
status: open
backlog-items: [AI-01, AI-02, AI-03, AI-04, AI-05, AI-16, AI-19, AI-20, AI-21, P3-04, P3-07, F2-04]
related:
  - 2026-07-11-es-analytics-integration.md
  - ../backlog/AI-IMPROVEMENTS.md
  - ../architecture/services/categorization-and-ai-services.md
  - ../../docs/adr/0004-analytics-elasticsearch-read-store.md
---

# AI-service on the ES read-store — structured intents, hybrid search, slot filters, cleanup

## Goal

Make the analytics-service Elasticsearch read-store the data backbone of ai-service chat:
structured intents answered by exact ES aggregations (AI-19), semantic transaction search
served by ES hybrid BM25+kNN instead of ChromaDB (AI-20), and category/amount slot
filters actually working end-to-end (AI-02/AI-21) — all measured against a new eval
harness (AI-01), with the ai-service junk removed and the decorative ports made real.
Done when: eval harness runs in CI-able form, all four intents answer without touching
the legacy gateway REST dashboard, hybrid ES search beats the ChromaDB baseline on the
golden set, ChromaDB + manual ingest are deleted, and the chat UI renders sources instead
of a JSON stub.

## Context

- ADR-0004 cutover is live and verified (plan 2026-07-11, session 2026-07-12): ES indices
  `transactions/accounts/taxonomy/goals` (physical `*_v1` behind aliases, danish-analyzed
  `description` + `.raw`, denormalized `category_name`/`subcategory_name`, `amount_abs`),
  event-synced projection consumer, JWT-authed `/api/v1/analytics/*` API.
- **Code survey 2026-07-12** (grounding for this plan):
  - ai-service **never calls analytics-service**. `app/adapters/outbound/analytics_client.py`
    is misnamed — it fans out to transaction-service (`largest_expense`, 200-row fetch +
    client-side sort, documented miss risk), gateway legacy REST `/api/v1/dashboard/overview/`
    (`category_breakdown` — the last consumer blocking ADR-0004 legacy-path deletion), and
    budget-service (`budget_status`). No `ANALYTICS_SERVICE_URL` in config or compose.
  - `transaction_search` = ChromaDB (`chromadb_search.py` + `vectorstore.py`, embedded
    `PersistentClient`, single `transactions__<model>` collection, `user_id` metadata
    tenancy). Ingest is manual full re-fetch + re-embed (`ingest_service.py`) — **but it no
    longer blocks the event loop** (P1-09 fixed it via `anyio.to_thread`; the architecture
    doc's CRITICAL claim is outdated). Ghost data / no event sync remains (P3-04).
  - Router (`ollama_router.py`) only ever emits `slots={"query"}`; the
    `_slots_to_filters` translation in `intent_dispatcher.py:105` (category/amount_min/
    amount_max/is_expense) and the `category` filter in `_dispatch_largest_expense` are
    unreachable (audit M24). `amount_min`/`amount_max` clobber bug present.
  - Ports (`application/ports/`) are decorative AND signature-drifted (adapters return
    `(result, elapsed_ms)` tuples; ports don't) — nothing types against them.
  - Junk: `test_chromadb_sanity*/` (binary vector DBs, personal data), broken
    `scripts/sanity_check_retrieval.py` (imports deleted `app.application.retriever`),
    committed `.pytest_cache/`. Compose sets dead env `LLM_MODEL` (config reads
    `LLM_ROUTER_MODEL`/`LLM_RESPONDER_MODEL`).
  - ES has **no `dense_vector` field** yet on any index.
  - Frontend chat: SSE events all handled (`intent_resolved/data_ready/prose_chunk/done/
    error`); `ChatMessage.jsx` renders `data_ready` payload as a raw JSON `<pre>` stub
    (`TODO PR 3: DataPanel-dispatcher`); no citations, no feedback UI; history is
    client-side only and never sent to the backend.
- **Machine constraint** (session 2026-07-12): responder model `qwen3:8b` lives on the
  other dev machine — do not change model config; eval harness must have a
  retrieval-only mode that doesn't need the responder.

## Non-goals

- No change to taxonomy ownership (categorization-service stays sole writer, ADR-003) or
  to who writes ES documents' core fields (analytics-service projection consumer).
- No change to the SSE event contract consumed by the frontend (new event types may be
  added, existing ones stay stable) and no change to router/responder model config.
- `budget_status` stays on budget-service (budgets are not projected into ES).
- No multi-hop agentic loop (AI-10), no intent pre-classifier (AI-14), no proactive
  insights (AI-17) — sequenced later per AI-IMPROVEMENTS.
- gateway's own analytics reads are untouched (already cut over).

## Steps

Ordered = priority order. Steps 1–3 are independent of each other after step 1.

### 0. AI-01 — eval harness (gate for everything below)

1. [x] `services/ai-service/tests/eval/` — golden set of ~50 Danish Q/A over a fixture
   dataset (exact-merchant, category, aggregation, date-range, amount-filter, negation).
   Sources: NOTES.md sanity cases + the intent of the broken
   `scripts/sanity_check_retrieval.py` (absorb, then delete the script). Metrics:
   recall@k / MRR for retrieval; numeric-correctness for structured intents. pytest
   marker `eval`, retrieval-only mode (no responder). Baseline the current ChromaDB
   pipeline before touching anything.
   *(2026-07-12: built — 20 retrieval + 16 intent + 14 aggregation cases over a
   43-tx fixture set (`tests/eval/`), drift-guarded by a no-Ollama self-check that runs
   in the normal suite. `make test-eval` runs the live part; `make test` excludes marker
   `eval`. **Baseline: retrieval recall@10 = 1.000, MRR = 1.000 (20 cases); intent
   accuracy = 1.000 (16/16).** Caveat: the small fixture corpus saturates both metrics —
   they guard regressions but won't discriminate AI-20 improvements; add distractor docs
   + harder cases when discrimination is needed. Floors set at 0.95/0.95/0.90.
   Aggregation cases are data-only until a live-backend numeric eval exists.)*
   *(2026-07-13: **hardened for AI-20 discrimination** — 22 distractor txs (ids 100+,
   real Danish orthography, semantically adjacent categories without CATEGORY_SYNONYMS
   coverage), 15 hard retrieval cases (cross-spelling "Føtex"→"Foetex", world-knowledge
   "musik"→Spotify, near-distractor discrimination), 6 harder intent phrasings, and
   **recall@3** added as the sharp metric. New baseline (35 retrieval / 22 intent cases):
   recall@10 = 1.000 (still saturated), **recall@3 = 0.967, MRR = 0.981, intent = 0.955**
   — signal carried by "tøj shopping" (recall@3 0.33), "el og vand regninger" (0.50) and
   the "bid af samlede forbrug" intent miss. AI-20 cutover gate: compare recall@3/MRR,
   not recall@10. Floors 0.95/0.95/0.95, intent 0.90.)*

### 1. AI-19 — structured intents → analytics-service (S)

2. [x] `services/ai-service/app/config.py` + `docker-compose.yml` (+ k8s overlay): add
   `ANALYTICS_SERVICE_URL` (compose: `http://analytics-service:8000`); while in compose,
   delete the dead `LLM_MODEL` env on ai-service. *(2026-07-12: done; also removed dead
   `GATEWAY_SERVICE_URL` from ai-service config/compose + `LLM_MODEL` from k8s configmap;
   ai-service `depends_on` gateway → analytics. k8s uses the shared configmap which
   already had `ANALYTICS_SERVICE_URL`.)*
3. [x] Split/repoint `app/adapters/outbound/analytics_client.py`:
   `largest_expense` → `GET /api/v1/analytics/transactions?tx_type=expense&…` sorted by
   `amount_abs` desc in ES; `category_breakdown` → `GET /api/v1/analytics/overview`.
   Budget client stays. **Check first** whether `/analytics/transactions` supports a sort
   param — if not, add `sort=amount_desc` (or a `top-expenses` variant) to
   analytics-service `rest_api.py`/`query_store.py` (small, additive).
   *(2026-07-12: no sort param existed → added `sort ∈ {date_desc, amount_desc}` through
   rest_api/query_service/port/query_store, sorting on `amount_abs` with
   `transaction_id` tiebreak; unit + integration tests added. Client repointed; category
   slot still filters client-side on name over a 200-row page until AI-21.)*
4. [x] Forward the user JWT (ai-service already holds it) — analytics endpoints are
   JWT-authed. Update dispatcher tests; add an eval case for the documented
   ">200 rows largest-expense miss" now being exact. *(2026-07-12: new
   `tests/unit/test_analytics_client.py` pins endpoint/params/mapping at the `_get_json`
   seam; integration stream-test updated to the analytics response shape; golden
   aggregation case notes the ES-sort contract.)*
5. [x] Result: ai-service no longer calls gateway legacy REST → note it in ADR-0004's
   cleanup checklist (legacy dashboard path becomes deletable). *(2026-07-12: noted in
   ADR-0004 §Oprydning.)*

### 2. Cleanup batch (S, mostly deletions)

6. [x] Delete `services/ai-service/test_chromadb_sanity/`, `test_chromadb_sanity_v2/`
   (P3-07 — personal data in repo), `scripts/sanity_check_retrieval.py` (absorbed by
   step 1), committed `.pytest_cache/`; extend `.gitignore`. *(2026-07-12: the sanity
   dirs + `.pytest_cache` turned out to be untracked and already gitignored — deleted
   from disk; the broken script was tracked → `git rm`; `scripts/` removed.)*
7. [x] Make ports real (they become the AI-20 seam): align `IAnalyticsPort` /
   `ISemanticSearchPort` signatures with reality (the `(result, elapsed_ms)` tuples),
   type `intent_dispatcher.py` + `pipeline.py` against the ports, and extend
   `test_architecture.py` to assert adapters conform (resolves the "wire or delete"
   half of P3-04). *(2026-07-12: all four ports aligned + `@runtime_checkable`;
   dispatcher now typed against `IAnalyticsPort`/`ISemanticSearchPort`;
   `test_architecture.py` got isinstance-conformance + parameter-signature drift
   tests. `pipeline.py` still constructs the concrete adapters — that construction
   site is where AI-20's `SEARCH_BACKEND` flag will branch.)*

### 3. AI-20 — ES hybrid search replaces ChromaDB (M)

8. [x] *(2026-07-13: recorded — [decisions/2026-07-13-embed-worker-placement.md](../decisions/2026-07-13-embed-worker-placement.md).)*
   **Decision (record via dev-notes-decision before coding):** where does the
   embedding writer live? Recommendation: a second consumer **inside analytics-service**
   (queue `analytics.embeddings` on `transaction.*`) that calls Ollama `embed` (bge-m3)
   and partial-updates only the `description_vector` field — ES writes stay within the
   owning service, Ollama outages can't stall the main projection queue, and DLQ/retry
   piggybacks the existing consumer pattern. Rejected alternatives to note: embedding in
   the main projector (couples core projections to Ollama uptime), ai-service writing to
   ES directly (breaks store-per-service ownership).
9. [ ] `analytics-service mappings.py`: `transactions_v2` physical index with
   `description_vector: dense_vector` (1024 dims, cosine, bge-m3) — alias-swap reindex
   per ADR-0004's documented pattern; backfill embeddings via a variant of
   `app/tools/backfill.py`.
10. [ ] New analytics endpoint (keeps ES access in one service): hybrid search —
    BM25 on danish `description` + kNN on `description_vector`, RRF, filters
    (`user_id`, dates, `category_id`/`subcategory_id`, `tx_type`, amount range on
    `amount_abs`). ai-service embeds the query itself (it owns Ollama) and sends
    text + query_vector.
11. [ ] ai-service: new `es_search.py` adapter implementing `ISemanticSearchPort`;
    cutover flag `SEARCH_BACKEND ∈ {chroma, es}` (default chroma until eval passes).
    Run the AI-01 golden set against both; flip default when ES ≥ ChromaDB baseline.
12. [ ] Post-cutover deletion: `chromadb_search.py`, `vectorstore.py`,
    `ingest_service.py`, `ingest_api.py`, chromadb dependency, `CHROMADB_PATH`, the
    frontend's ingest trigger if any. Resolves AI-06/AI-11/AI-18/P3-04 in one move;
    unblocks F2-04 (search UI) since staleness is gone (event-synced index).

### 4. AI-02 + AI-21 — activate slots + taxonomy resolution (S)

13. [ ] `ollama_router.py`: few-shot the router into emitting `category`,
    `amount_min`/`amount_max`, `is_expense` slots; fix the min/max clobber bug (M24)
    in `intent_dispatcher._slots_to_filters` with a regression test.
14. [ ] Resolve `category` slot text → `category_id`/`subcategory_id` via the ES
    `taxonomy` index (keyword + fuzzy on `name`; expose as a small analytics endpoint,
    e.g. `GET /analytics/taxonomy/resolve?name=`). IDs are the grouping key (ADR-003),
    never names. Feed the resolved ids into hybrid-search filters and
    `largest_expense`/`category_breakdown` params.

### 5. Wave-A responder hardening (S each, after AI-19)

15. [ ] AI-05 numeric guardrail: all sums/counts computed in code, injected as a FACTS
    block in `_format_data_context()`; post-check streamed prose for out-of-context
    amounts. AI-03 (aggregation guard) is largely *delivered by* AI-19 — add the eval
    cases proving aggregate questions never come from top-K vectors.
16. [ ] AI-13 clarify + AI-15 thinking: emit a `clarify` SSE event below a router
    confidence threshold (confidence already returned, unused); A/B `think=False` on
    the responder against the eval set (latency vs. quality) — measure, don't guess.

### 6. UI (frontend, can run parallel to 3–5)

17. [ ] **AI-04 citations / DataPanel** — replace the `ChatMessage.jsx` JSON stub with
    the planned DataPanel-dispatcher per intent: transaction list ("baseret på disse
    transaktioner", linking to the transactions page), category-breakdown mini-viz,
    budget bars. Data already rides the `data_ready` event; no backend change.
18. [ ] **AI-16 feedback** — 👍/👎 per answer storing question/intent/retrieved ids
    (tiny ai-service table); feeds the golden set.
19. [ ] **AI-12 multi-turn (cheap version)** — history already lives in `chatReducer`;
    send last N turns in the request body, router prompt inherits intent/period/slots
    unless overridden. No server-side session storage.
20. [ ] **F2-04 semantic search box** on the transactions page backed by the new hybrid
    endpoint (post step 3 — the P3-04 staleness blocker is gone).
21. [ ] `clarify` event rendering (pairs with step 16) + render source-count/hop info
    from `MessageMetadata`.

### Verification

- [ ] `make -C services/ai-service test` and `make -C services/analytics-service test`
  green at every step; `npm test` in `services/frontend` for steps 17–21.
- [ ] Eval harness: baseline report (ChromaDB) vs. post-AI-20 report (ES hybrid) —
  recall@k/MRR must not regress; aggregation cases must be numerically exact.
- [ ] `make test-e2e` with compose up; manual smoke: all four intents in the chat UI,
  danish stemming ("netto"), a slot-filtered question ("udgifter over 500 kr i marts"),
  citations rendering. Responder-path smoke only on the machine that has `qwen3:8b`.

## Risks & rollback

- **ES reindex to `transactions_v2`** — alias swap is the documented ADR-0004 pattern
  and projections are rebuildable (backfill tool); rollback = point alias back to `_v1`.
- **Embedding backfill cost/latency** — bge-m3 over the full history via Ollama is slow
  (~100s per 262 tx measured on ingest); run per-user like the existing backfill,
  off-peak; the hybrid endpoint must degrade to BM25-only when the vector is missing.
- **Search-quality regression on cutover** — mitigated by the `SEARCH_BACKEND` flag +
  AI-01 gate; rollback = flip flag back to `chroma` (don't delete ChromaDB code until
  the flag has baked).
- **Analytics API drift** — ai-service becomes a second consumer of
  `/api/v1/analytics/*`; contract changes now have two clients. Keep the DTOs additive;
  the gateway tests + new ai-service client tests both pin the contract.
- **Ollama unavailability** — embed-worker must DLQ/retry without blocking core
  projections (hence the separate queue in step 8); chat falls back to BM25-only.
- **Router prompt changes (step 13) regress intent accuracy** — eval set includes
  intent-classification cases; compare before/after.

## Outcome (fill in when done)

—
