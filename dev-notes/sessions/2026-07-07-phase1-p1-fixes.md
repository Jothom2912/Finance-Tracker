---
date: 2026-07-07
topic: Phase 1 — P1 critical fixes (all 12 items)
---

# Session 2026-07-07 — Phase 1 P1 fixes

Executed all 12 P1 backlog items from [plans/2026-07-07-refactoring-roadmap.md](../plans/2026-07-07-refactoring-roadmap.md) Phase 1. Seven services fixed in parallel + repo-hygiene done directly. **Functionality-preserving**; each service has new regression tests, all green. **Not committed** (awaiting review).

Footprint: 43 files, +1148/−421. (`services/frontend/package-lock.json` change is pre-existing, unrelated.)

## Done (by item)

- **P1-01 / P1-02 (budget)** — `close_month` fails closed: `TransactionPort` raises `UpstreamServiceUnavailable` on HTTP error → 503, no close, no event (`get_summary` keeps documented graceful degradation). All monthly-budget endpoints now filter by JWT `user_id` (cross-user → 404, verified to DB: `closed_at` NULL, no outbox row). Legacy `/api/v1/budgets` checked — already safe. Tests 16→23 unit, 34→42 integration.
- **P1-03 (banking)** — ownership checks on `disconnect` + `list_connections` (reused `_verify_account_access` / connection `user_id`); non-owner → 403, no side effects. Tests 8→16.
- **P1-04 / P1-12-saga (saga)** — new `app/auth.py` (HS256, required `JWT_SECRET`); status endpoint requires JWT + `context.user_id` ownership (403), response strips `fetched_items`/`items` (kept every field gateway/frontend read). Orchestrator `handle_compensation_reply` now takes `success` — failed rollback → saga `failed`, rewind stops; added step-name validation. Tests 25→32. Added `JWT_SECRET` to all 5 saga compose services; k8s already had it via secretRef.
- **P1-05 / P1-11 (account)** — auth dependency on all account-group routes (401 anon); `user.created` consumer got DLQ + `x-retry-count`≤3 retry (republish to own queue via default exchange — avoids the topic fan-out bug goal-service still has). Tests 17→22.
- **P1-06 (gateway+ai)** — removed empty-string secret defaults; both fail fast at startup (RuntimeError / pydantic ValidationError). conftest sets the var for tests.
- **P1-07 (gateway+transaction)** — tx-service: single `find_filtered()` repo method applies ALL filters + `OFFSET/LIMIT` in SQL (killed the mutually-exclusive elif dispatch + in-Python type filter); order `date desc, id desc` for stable pagination. Gateway: sends date range + paginates (page 200, cap 100), keeps client-side date filter as safety net, memoizes tx + category-map per request; forwards `Authorization` to saga-service. REST contract unchanged. Tests: gateway 7→21, tx 171→177.
- **P1-09 / P1-10 (ai)** — ingest blocking work moved to `anyio.to_thread`; ChromaDB collection now versioned `transactions__{model}` resolved by one shared function (ingest + search); full-collection wipe path removed (mismatch now raises). Tests +6.
- **P1-08 (repo)** — untracked `scripts/backups/*.jsonl` (PII) + gitignored `scripts/backups/`; parameterized compose EB block (`ENABLE_BANKING_SANDBOX_APP_ID`/`_PEM_PATH` with dev defaults), documented in example.env. Used sandbox-prefixed names so they don't collide with the production `ENABLE_BANKING_*` in the auto-loaded `.env`.

## Deploy actions required (do NOT skip)

1. **RabbitMQ**: delete (after draining) the `account_service.account_creation` queue once so it recreates with the new dead-letter arguments (RabbitMQ rejects redeclaration with changed args — PRECONDITION_FAILED). Documented in-code at the declaration site.
2. **AI vectors**: users must re-ingest once — search now targets `transactions__bge-m3`; old `transactions` collection is left intact, a startup warning flags it.
3. **Secrets**: `JWT_SECRET`/`SECRET_KEY` are now required in gateway, ai, saga (+ workers). Compose/k8s already provide them; any other launch env must set them or the service crashes at startup (by design).

## Learned / surprised

- Two consumers still republish retries to the topic exchange (fan-out bug) — account-service's new consumer avoids it; goal-service's original still has it → folded into P2-19.
- budget `create` uniqueness is `(account_id, month, year)` not user-scoped — latent cross-user 500; accounts are single-owner so not exploitable now.
- account-groups have no owner column — authenticated but not ownership-scoped; genuine limitation, not a quick fix.

## Open ends / decisions needed

- **Commit**: changes are staged in the working tree, not committed. Recommend one commit per service (or one Phase-1 commit) once reviewed.
- **User decision**: git history rewrite (filter-repo) for the purged PII backup — only needed if the repo will ever be shared. (C9)
- **Next**: Phase 2 — extract `services/shared/messaging` + `shared/auth` (P2-01/02/03), the keystone that de-duplicates 8× outbox / 9× auth and makes the remaining hygiene fixes single-point.

## Notes updated
- backlog/BACKLOG.md (P1 all → done + carry-over notes), findings/2026-07-07-architecture-audit.md (C1–C10, H3/H4/H6/H14 tagged ✅, status → in-progress), 00-INDEX.md.
