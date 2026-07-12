---
date: 2026-07-12
topic: Wave 1 of plan 2026-07-12-ai-service-es-chat — AI-01 eval harness, AI-19 structured intents → analytics-service, ai-service cleanup (junk + ports)
---

# Session 2026-07-12 — ai-service on ES, wave 1 (AI-01 + AI-19 + cleanup)

Executed steps 0–2 of [plans/2026-07-12-ai-service-es-chat.md](../plans/2026-07-12-ai-service-es-chat.md).

## Done

- **AI-01 eval harness** (`services/ai-service/tests/eval/`): 43-tx deterministic
  fixture set, 20 retrieval + 16 intent + 14 aggregation golden cases, recall@10/MRR +
  intent-accuracy metrics, tenant-isolation test. Marker `eval` excluded from
  `make test`; `make test-eval` runs live (compose-ollama on host port 11435 has
  bge-m3 + qwen3:4b). A no-Ollama self-check (drift guard: golden literals must be
  recomputable from fixtures) runs in the normal suite. Broken
  `scripts/sanity_check_retrieval.py` absorbed and deleted.
  **Baseline: retrieval recall@10 = 1.000, MRR = 1.000; intent accuracy = 1.000.**
  Both metrics are SATURATED by the small corpus — regression guard only; add
  distractor docs + harder cases before using it to discriminate AI-20.
- **AI-19**: analytics-service `/api/v1/analytics/transactions` gained
  `sort ∈ {date_desc, amount_desc}` (ES sort on `amount_abs`, `transaction_id`
  tiebreak) through rest_api/query_service/port/query_store. ai-service
  `analytics_client.py` repointed: `largest_expense` → `/analytics/transactions`
  (exact server-side sort, kills the 200-row miss risk), `category_breakdown` →
  `/analytics/overview`; `budget_status` unchanged (budgets not in ES).
  `ANALYTICS_SERVICE_URL` added (config/compose; k8s shared configmap had it);
  dead `GATEWAY_SERVICE_URL` + `LLM_MODEL` env removed (compose + k8s configmap);
  ai-service compose `depends_on` gateway → analytics. ADR-0004 §Oprydning updated:
  **ai-service was the last consumer of gateway's legacy `/dashboard/overview/` —
  the legacy REST path is now freely deletable.**
- **Cleanup**: `test_chromadb_sanity*/` + `.pytest_cache` deleted from disk (were
  untracked + already gitignored). Ports made real: all four Protocols aligned to
  adapter reality (`(result, elapsed_ms)` tuples), `@runtime_checkable`; dispatcher
  typed against `IAnalyticsPort`/`ISemanticSearchPort`; `test_architecture.py` gained
  isinstance-conformance + parameter-signature drift tests. Ports-half of P3-04 done.

## Verified

- ai-service 77 passed (incl. 6 new client tests + self-checks + conformance),
  analytics unit 52 passed, ruff clean both, `docker compose config -q` ok.
- Integration test for `amount_desc` added to `test_query_store.py` (can't run here —
  testcontainer-ES OOM on the 3.8 GiB Docker VM; runs where analytics integration runs).
- **Live smoke in compose** (stack up, real backfilled ES data, dev-JWT):
  `/analytics/transactions?sort=amount_desc` → 206 expenses correctly descending;
  in-container `AnalyticsClient.get_largest_expenses('2026-04')` → top-5 exact
  (135 ms) and `get_category_breakdown('2026-04')` → 8 id-keyed categories (287 ms).

## Learned / gotchas

- **Docker VM (3.8 GiB) cannot load qwen3:4b with the full stack running** — Ollama
  needs 3.0 GiB free, ~2.3 available → chat-stream smoke via the router is impossible
  on this machine with everything up. The intent-eval baseline was run against HOST
  Ollama (11434, same qwen3:4b weights). Full SSE-pipeline smoke (router→dispatch→
  responder) still pending on the machine that has qwen3:8b (responder was already
  untested there — unchanged open end).
- Ollama's model runner dies transiently ("unexpected EOF") under memory pressure —
  intent eval got a one-retry-per-case guard.
- Windows curl mangles `ø` in inline JSON (cp1252) → ai-service 400 "error parsing
  body"; send UTF-8 payloads via `--data-binary @file`.
- Git Bash here has no `$TMPDIR` — write scratch files via explicit scratchpad path.

## Open ends / next (per plan)

- Wave 2 = AI-20 (ES hybrid search replaces ChromaDB): record the embed-worker
  placement decision (recommendation: separate consumer inside analytics-service on an
  `analytics.embeddings` queue) via `dev-notes-decision` BEFORE coding; then
  `transactions_v2` mapping + hybrid endpoint + `SEARCH_BACKEND` flag.
- Then AI-02+AI-21 (slots + taxonomy resolve), wave-A responder hardening
  (AI-05/13/15), UI steps 17–21 (DataPanel/citations first).
- Eval hardening when AI-20 needs discrimination: distractor docs, negation cases,
  larger corpus; numeric answer-eval against live backends.
- Nothing committed yet this session — working tree holds AI-01+AI-19+cleanup.
