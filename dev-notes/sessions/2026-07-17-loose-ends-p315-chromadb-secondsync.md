---
date: 2026-07-17
topic: Loose ends closed — P3-15 chunking, ChromaDB deletion (plan step 12), live second-sync dedup verified
---

# Loose ends: P3-15 + ChromaDB deletion + second-sync verification

Context: exam is DONE (user confirmed today) — the project continues as a hobby/portfolio
project; nothing is gated on exam timing anymore. This session closed the three loose
ends left from the P2-09 session before picking the next feature track.

## Done

### P3-15 — saga bulk-import chunking (`2cce0a09`)

`BulkCreateTransactionDTO.items` is bounded 1..500; an EB fetch with 0 or >500 items
ValidationError'ed `_handle_bulk_import` → 3 retries → saga failure. Fix in
transaction-service `saga_command_consumer.py`:

- 0 items → success reply (0 imported) without touching the DB — an empty fetch is a
  successful sync, not an error.
- >500 items → sequential chunks of 500 (`BULK_IMPORT_CHUNK_SIZE`), each chunk in its own
  UoW/session, counts + `imported_ids` aggregated across chunks in the reply.
- A mid-chunk crash propagates to the existing retry path; re-running all chunks is
  idempotent because P2-09 dedup (external_id + fuzzy fallback) skips committed rows.
  Accepted trade-off: on terminal failure, earlier chunks stay committed (they are real
  bank transactions; the next sync would import them anyway) — the failure reply carries
  no partial `imported_ids`, same honesty semantics as before.
- DTO bounds kept as the public-contract limit on the API path.

Tests: zero-items reply, 1001→500/500/1 chunking + aggregation + order. 161 unit + 35
integration green.

### ChromaDB + ingest flow deleted — AI-plan 2026-07-12 step 12 (`f03a55a4`)

`SEARCH_BACKEND=es` had baked 3 days (cutover 2026-07-14). Deleted: `chromadb_search.py`,
`vectorstore.py`, `ingest_service.py`, `ingest_api.py`, `transaction_client.py` (ingest
was its only consumer), `test_ingest.py`/`test_vectorstore.py`, chromadb dependency,
`CHROMADB_PATH`/`SEARCH_BACKEND`/`TRANSACTION_SERVICE_URL` from config+compose+k8s
configmap, compose volume `ai_chromadb_data`, k8s PVC + mounts, Dockerfile mkdir,
frontend "Opdater vidensbase" button + `api/ai.jsx` + dead CSS (the ES index is
event-synced — nothing for the user to trigger).

Moved, not deleted: `get_ollama_client` → new `app/adapters/outbound/ollama_client.py`
(router/responder still chat via the ollama package; `EsSearch._embed_query` uses httpx
directly). Eval fixtures got a local `TransactionDTO`. `build_search()` seam kept as the
construction point. Eval harness is ES-only now (`eval_collection` fixture gone).

Resolves AI-06/AI-11/AI-18 + P3-04 fully; unblocks F2-04 (search UI). Rollback from here
= `git revert` + `backfill_embeddings` (the ES index is rebuildable).

Verified: ai-service 91 tests + lint, frontend 234 tests + lint, `docker compose config`
+ `kubectl kustomize` both valid.

## Live second-sync dedup verification (P2-09) — PASSED

Rebuilt the full transaction image family + ai-service, restarted, triggered a real EB
sync on connection `ba120c29…` (user 1) via `POST /api/v1/bank/connections/{id}/sync`
(dev-JWT minted with the compose secret). Saga `ab30381e…` completed:
**total_fetched 214, duplicates_skipped 214, new_imported 0, errors 0** (parse_skipped 5).
Transaction table unchanged (230 rows / 8 external_ids for user 1). The 8 id-bearing rows
deduped on `(account_id, external_id)`, the pre-P2-09 history on the NULL-scoped fuzzy
fallback. Bonus: this sync ran through the NEW chunked consumer code (214 = one chunk).

## Learned / operational notes

- **EB sandbox PEM had been deleted from disk** (it is gitignored since P1-08, so nothing
  in the repo restores it); user re-added it today. **Standing instruction: use an EB
  sandbox account with a TEST USER for future sync smokes**, not the personal user-1
  connection. Check `ENABLE_BANKING_KEY_PATH` exists before live-smoking.
- Saga results live in `saga_instances.context_json` (75KB with `fetched_items` —
  select with `- 'fetched_items'`); `saga_step_log` has no result column.

## Open ends

- Backlog P2/P3 state: only P2-15 (k8s secrets) left in P2; next decision is the feature
  track (F1-04 goal-allocation demo story vs F1-02/03 categorization loop vs AI-plan tail
  steps 13–21: AI-21 slots, responder hardening, DataPanel/citations UI).
- Bandit Makefile-vs-CI flag divergence still awaits a user decision (see 2026-07-16 log).
- localStorage key `rag_ingested` lingers in browsers — harmless, never read now.
