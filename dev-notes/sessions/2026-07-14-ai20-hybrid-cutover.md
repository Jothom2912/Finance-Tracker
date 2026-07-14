---
date: 2026-07-14
topic: AI-20 implemented and cut over — ES hybrid search (BM25+kNN+RRF) replaces ChromaDB behind SEARCH_BACKEND flag; closes AI-06/AI-11/AI-18/P3-04, unblocks F2-04
---

# Session 2026-07-14 — AI-20: ES hybrid search implemented + cutover

Executed steps 9–11 of [plans/2026-07-12-ai-service-es-chat.md](../plans/2026-07-12-ai-service-es-chat.md)
(step 12, ChromaDB deletion, deliberately deferred until the flag has baked).

## Done (4 commits, one per phase)

1. **`114557a6` analytics fase 1** — `transactions_v2`: per-index versions in
   mappings; `description_vector` (dense_vector 1024/cosine/bge-m3),
   `embedding_event_ts` guard, danish text-subfields on category names.
   Bootstrap auto-migrates on version bump (create → `_reindex` → atomic alias
   swap; old physical kept for rollback). `EmbeddingProjector` (state-reading,
   `StaleProjectionError` → retry) + `embedding_consumer` on own queue
   `analytics.embeddings` per decision 2026-07-13 — retries republish DIRECTLY
   to own queue (topic-exchange republish would fan out to every other
   `transaction.*` consumer; the existing projection_consumer has that quirk,
   left untouched). `backfill_embeddings` tool (guarded, live-safe, `--re-embed`).
2. **`39f65e24` analytics fase 2** — `POST /api/v1/analytics/search/hybrid`:
   BM25 (multi_match over `description^2` + category-name text-subfields) and
   pre-filtered kNN run concurrently, fused client-side with RRF
   (`app/domain/ranking.py`, pure function — native ES RRF needs > basic
   license on 8.11). Degrades to BM25-only without `query_vector`; vector-less
   docs stay lexically searchable. `account_id` optional (chat searches across
   accounts, ChromaDB parity). Dims validated against mapping (422).
3. **`b3ab364e` ai fase 3** — `EsSearch` adapter (`ISemanticSearchPort`): embeds
   the query itself via Ollama (survives future vectorstore deletion), falls
   back to no-vector (BM25-only) on embed failure, translates domain filters
   (category→category_name interim; amount $gte/$lte→amount_min/max;
   is_expense→tx_type). `SEARCH_BACKEND ∈ {chroma, es}`; `build_search()` in
   pipeline.py is the seam. Conformance + signature-drift tests extended.
4. **`180e8f7a` + `85c471be` fase 4 + cutover** — retrieval eval parameterized
   over `SEARCH_BACKEND` (same flag as prod); `es_seed.py` seeds fixtures into
   compose-ES with id-offset 9M (can never clobber real docs), embeddings via
   analytics' own backfill tool (no prose duplication). Compose flipped to `es`.

## Cutover gate (35 retrieval cases, hardened golden set)

| metric | ChromaDB | ES hybrid |
|---|---|---|
| recall@10 | 1.000 | 0.996 |
| recall@3 (sharp) | 0.967 | **0.971** |
| MRR | 0.981 | 0.967 |

Judgment call: ES wins the designated sharp metric; the MRR delta is exactly
one case ("toej shopping" — BM25 lexically matches the *Shopping category* of
Flying Tiger/Bog & Idé; AI-21 category-resolve is the counter). "el og vand
regninger" improved 0.50 → 1.00 on recall@3. All floors green. Flipped, kept
rollback trivial (env flip; Chroma code stays until baked).

## Verified live (compose)

- v1→v2 migration ran automatically on consumer startup: 222 real docs
  reindexed, alias swapped, `transactions_v1` retained.
- Embedding backfill: 66 eval docs + 222 real docs, all vectorized.
- In-container smoke as user 1: `build_search` → `EsSearch`; "netto" → real
  NETTO transactions (284 ms warm); "udgifter til mad og dagligvarer" +
  period=2026-04 → correct April groceries (semantic + filter).
- Full suites green: analytics 122 (incl. 9 nye hybrid-integrationstests +
  bootstrap-migrationstest), ai-service 98.

## Learned / gotchas

- **kNN top-k returns ALL docs** (even cosine 0) — on a small corpus every doc
  is in both RRF lists, and rank1+rank3 (1/61+1/63) marginally beats
  rank2+rank2 (2/62). Integration test needed filler docs to model a real
  corpus. Worth remembering when reading RRF evals on tiny datasets.
- **Docker-VM OOM blocks router-path smoke here too** (qwen3:4b killed under
  full stack — same constraint as 2026-07-12). SSE-endpoint smoke gave only
  pings; adapter-level in-container smoke covers the AI-20 diff (router/
  responder legs unchanged). Full SSE smoke still pending a machine/stack
  combo with headroom.
- ai-service container must be `--build`-ed, not just restarted, to pick up
  new adapter code (obvious, but cost one confused smoke run).
- Eval-doc seeding uses id-offset 9_000_000 + fake users 9001/9002 in the
  LIVE index — harmless (all real queries filter user_id) but reseed requires
  re-running backfill_embeddings (delete_by_query wipes vectors too).

## Open ends / next

- **Step 12 (deletion) after bake**: chromadb_search.py, vectorstore.py,
  ingest_service.py, ingest_api.py, chromadb dep, `CHROMADB_PATH`, compose
  volume `ai_chromadb_data` — resolves AI-06/11/18/P3-04 fully; then raise
  eval floors to the ES baseline.
- k8s overlay: `SEARCH_BACKEND` not set there (defaults to chroma) — add to
  shared configmap ved næste k8s-runde; embedding-consumer deployment mangler
  også i k8s.
- AI-21 (slots + taxonomy resolve) is next per plan — hybrid endpoint already
  accepts category_id/subcategory_id/amount filters; also the counter to the
  "toej shopping" BM25-category-noise case.
- F2-04 (search UI) now unblocked — build against the hybrid endpoint.
