---
title: Integrate phase-1-fixes with master's Elasticsearch analytics read-side
date: 2026-07-11
status: open
backlog-items: [P2-04, AI-03, AI-06, AI-11, AI-18, AI-19, AI-20, AI-21, ML-02, ML-13, ML-15]
related:
  - ../sessions/2026-07-07-phase1-p1-fixes.md
  - ../sessions/2026-07-07-phase2-in-flight.md
  - ../../docs/adr/0004-analytics-elasticsearch-read-store.md
---

# Integrate phase-1-fixes with master's Elasticsearch analytics read-side

## Goal

Land the local P1+P2 work (branch `phase-1-fixes`: 2 commits + large uncommitted working
tree) on top of `origin/master`'s 14 new commits (analytics-service + Elasticsearch
read-side, gateway dual-read/cutover per ADR-0004), bring the ES stack up correctly
locally, and re-verify the cutover. Done when: rebased branch is green (`make test`),
compose stack runs with ES + projection consumer + backfilled data, and a `dual`-mode
re-verification shows zero divergences on overview/expenses-by-month.

## Context

- **Master side** (commits `fe9d1a8d`..`f17c104f`): new `analytics-service` owning ES
  8.11.4 — 4 indices (`transactions`, `accounts`, `taxonomy`, `goals`; physical `*_v1`
  behind aliases, `dynamic: strict`, amounts `scaled_float(100)`, danish analyzer on
  `description` + `.raw`). Projection consumer (`app/workers/projection_consumer.py`,
  queues `analytics.{transactions,accounts,taxonomy,goals}` + DLQs), query API
  `/api/v1/analytics/*`, backfill tool (`app/tools/backfill.py`, per-user, live-safe via
  `event_ts=0` guards). Gateway: `IFinancialAnalyticsPort`/`IAnalyticsInsightsPort`,
  `ANALYTICS_READ_SOURCE ∈ {legacy, dual, analytics}` — **already flipped to `analytics`**
  in compose + k8s configmap; cutover verified 2026-07-11 (ADR-0004).
- **Local side**: `phase-1-fixes` = P1 subset commit + KB commit, plus uncommitted
  working tree containing the P1 remainder and the interrupted Phase 2 work (shared
  auth/domain/messaging packages built-not-adopted, gateway `http_client.py` +
  memoization + async port conversion, saga/frontend/etc. — see
  [sessions/2026-07-07-phase2-in-flight.md](../sessions/2026-07-07-phase2-in-flight.md)).
- Conflict analysis (2026-07-11): overlap is small and concentrated in gateway. Trivial:
  `docker-compose.yml`, gateway `config.py`. Semantic: gateway
  `application/ports/outbound.py` + `graphql_api.py` (local async conversion + memoization
  vs master's new sync analytics-port stack), and frontend
  `useDashboardData.jsx` (master's `DASHBOARD_QUERY` rewrite vs local `useGoals()`
  extraction). `shared/auth` deletion is safe — nothing on master imports it (master's new
  services carry their own `app/auth.py`). Frontend deletions don't collide.

## Non-goals

- No behavior change to master's analytics/ES read-side itself — we integrate on top of
  it, we do not redesign it.
- No adoption ("wave B") of the shared auth/messaging/domain packages by services in this
  plan — that stays deferred per the Phase 2 session note.
- The GraphQL schema and REST contracts stay unchanged for the frontend.
- The ES *improvement* proposals (§Improvements below) are queued as backlog items, not
  executed here.

## Steps

### A — Secure and reconcile the working tree

1. [ ] **Commit the working tree on `phase-1-fixes`** in logical chunks (e.g. one commit
   for P1-remainder, one for the shared packages, one per-service P2 batch, one for
   frontend P2-17/18). Nothing may stay uncommitted through a rebase. Untracked test
   conftests (`services/gateway-service/tests/conftest.py` — sets `SECRET_KEY` for tests)
   MUST be included: master's new gateway tests import `app.config`, which now fail-fasts
   without it.
2. [ ] **Settle the gateway async/sync question before rebasing** (it is the one genuine
   semantic incompatibility): local P2-04 made `IAnalyticsReadRepository` methods async,
   but master's new `LegacyFinancialAnalyticsAdapter` → `AnalyticsService` →
   `HttpAnalyticsReadRepository` chain is synchronous — a textually-clean merge would
   hand coroutines to sync callers at runtime. **Decision: do not finish the async
   conversion on the legacy read path.** ADR-0004 schedules that whole chain (legacy
   adapter, dual-read wrapper, `HttpAnalyticsReadRepository`, gateway `AnalyticsService`
   aggregation) for deletion one release after cutover; async-ifying code slated for
   deletion is wasted and risky. Concretely: revert the local async signatures on the
   read-side ports/clients to sync, keep the local per-request memoization
   (`_MemoizedAnalyticsReadRepository`, `_category_name_map` cache) inside the legacy
   branch, and keep `http_client.py` (shared client helper) for the clients that survive
   cutover. **Note the legacy REST `/api/v1/dashboard/overview/` cannot be deleted yet:
   ai-service's `category_breakdown` intent consumes it** (see AI-19).
3. [ ] **Rebase `phase-1-fixes` onto `origin/master`** (`git rebase origin/master`).
   Expected manual resolutions (keep-from-each-side table from the conflict report):
   - `docker-compose.yml` — keep master's ES/analytics blocks + local's enable-banking
     anchors and saga `JWT_SECRET`s (disjoint hunks).
   - `services/gateway-service/app/config.py` — keep local `SECRET_KEY` fail-fast (top) +
     master `ANALYTICS_*` settings (EOF).
   - `services/gateway-service/app/application/ports/outbound.py` — keep master's two new
     port classes; apply step-2 decision (sync read-side signatures).
   - `services/gateway-service/app/adapters/inbound/graphql_api.py` — keep master's
     `build_financial_analytics_port` + context keys; re-inject local memoization wrapper
     into the `legacy` branch only.
   - `services/gateway-service/app/application/service.py` — keep local memoization; take
     master's cosmetic reformat or drop it.
   - `services/frontend/src/hooks/useDashboardData/useDashboardData.jsx` — take master's
     `DASHBOARD_QUERY` rewrite wholesale, re-apply local's `useGoals()` swap on top
     (local-only `useGoals.jsx` survives untouched).
4. [ ] **Post-rebase consistency sweep**: grep gateway for stray `await` on now-sync
   read-repo calls and vice versa; `python -m py_compile` over changed files; run
   `npm install` in `services/frontend` (lock drifted locally).

### B — Bring the ES stack up correctly (deploy/run order)

5. [ ] **Secrets/env**: ensure `.env` provides `SECRET_KEY` (gateway/ai fail-fast now),
   `JWT_SECRET` for saga services (P1) AND analytics-service — analytics `JWT_SECRET`
   must equal the platform JWT signing secret or every `/api/v1/analytics/*` call 401s.
   Compose defaults exist for dev; k8s uses `finance-tracker-secrets`.
6. [ ] `docker compose up -d elasticsearch analytics-service analytics-projection-consumer`
   — ES is single-node 8.11.4, xpack off, healthcheck-gated. Index bootstrap is automatic
   and idempotent (`ensure_indices` on startup of API/consumer/backfill).
7. [ ] **One-time P1 deploy actions** (from the P1 session log, still pending): drain +
   delete RabbitMQ queue `account_service.account_creation` so it recreates with DLQ
   args; note AI re-ingest targets `transactions__bge-m3`.
8. [ ] **Backfill history**: `docker compose run --rm analytics-service python -m
   app.tools.backfill --user-id <N>` per user (idempotent, live-safe; taxonomy seeded
   first). Confirm doc counts in the report output.
9. [ ] **Re-verify the cutover under the merged code**: set gateway
   `ANALYTICS_READ_SOURCE=dual`, click through dashboard + transactions + search, then
   `docker logs gateway-service | grep analytics.dual_read`. Criterion (per ADR-0004):
   zero divergences on overview/expenses-by-month; order-only divergence on
   limit-truncated transaction lists is expected. Then flip back to `analytics`.
   Rollback at any point = `ANALYTICS_READ_SOURCE=legacy`.

### C — Verification

10. [ ] Gateway: `make -C services/gateway-service test` (master's 5 new analytics test
    files + local's memoization/auth-forwarding/secret tests must all pass together).
11. [ ] Analytics: `make -C services/analytics-service test`.
12. [ ] The Phase-2 "resume procedure" per-service suites (user, goal, budget,
    transaction, categorization, banking, saga, ai, account) — treat Docker-dependent
    failures as infra. Then `make test`, and `make test-e2e` with the compose stack up.
13. [ ] Frontend: `npm test` in `services/frontend` (master added
    `useTransactionSearch`/`MonthComparison` tests; local changed `useDashboardData`).
14. [ ] Manual smoke: dashboard month-picker + subcategory drilldown (F4 behavior must
    survive the analytics-backed `periodOverview`), transaction free-text search (danish
    stemming), AI chat `category_breakdown` intent (depends on legacy REST dashboard —
    must still answer).

## Risks & rollback

- **Async/sync mismatch resurfacing** — the failure mode is silent (coroutine never
  awaited → empty/broken responses, not exceptions at import). Detection: step 4 grep +
  gateway unit tests + step 14 smoke. Rollback: `ANALYTICS_READ_SOURCE=legacy` only
  rescues reads that the legacy path serves; a broken legacy path has no flag — hence the
  decision to keep it sync/minimal.
- **Rebase goes sideways** — pre-rebase safety tag (`git tag pre-es-rebase`), and the
  working tree is fully committed first (step 1), so `git rebase --abort` / reset to tag
  is always available.
- **Backfill against un-fixed transaction-service pagination**: backfill guards against
  `find_by_account` ignoring skip/limit by stopping on repeated pages — but local P1-07
  *fixed* pagination; after rebase both behaviors are safe. No action, just awareness.
- **ES resource pressure**: 1 GiB compose mem-limit / 512 MB heap is dev-sized; k8s prod
  needs xpack auth + TLS + snapshots + replicas>0 (ADR-0004 outstanding hardening).
- **`RABBITMQ_URL` for the k8s projection consumer** — verify the shared configmap
  actually provides it (flagged unverified during mapping); missing → consumer silently
  uses the compose-default guest URL and fails.

## Improvements queued (unified ES for chat + category/subcategory)

Recorded as backlog items (AI-19..AI-21 in
[backlog/AI-IMPROVEMENTS.md](../backlog/AI-IMPROVEMENTS.md)); summary and rationale:

1. **AI-19 — re-point ai-service structured intents to `/api/v1/analytics/*`.**
   `largest_expense` (today: 200-row fetch + client-side sort — documented miss risk) →
   ES sort/top-hits via `/analytics/transactions`; `category_breakdown` (today: gateway's
   legacy in-memory REST aggregation) → `/analytics/overview`. This *implements* AI-03's
   aggregation guard with exact aggregations, removes ai-service's dependency on the
   legacy REST dashboard, and unblocks ADR-0004's cleanup of the legacy path.
2. **AI-20 — ES as the chat search backend (hybrid BM25 + kNN), replacing ChromaDB.**
   The `transactions` index already has danish-analyzed `description` + denormalized
   `category_id/name`, `subcategory_id/name` and is event-synced (projection consumer) —
   which by itself solves ChromaDB's ghost-data/manual-full-re-ingest problem (AI-11,
   P3-04). Add a `dense_vector` field (bge-m3, 1024 dims) to the transactions mapping
   (new physical `transactions_v2` behind the alias), have the projector (or a small
   embed-worker) populate it, and implement `ISemanticSearchPort` with an ES hybrid query
   (BM25 + kNN, RRF) — this is AI-06 delivered on shared infra, and resolves AI-18
   (embedded-ChromaDB single-replica cap) in favor of "ES already in the stack".
   Seam: `services/ai-service/app/adapters/outbound/chromadb_search.py` (adapter swap;
   ports are decorative — type against the adapter). Gate on AI-01 eval harness.
3. **AI-21 — category/subcategory-aware chat filters via the `taxonomy` index.**
   Activate the dead slot→filter path (AI-02) and resolve the router's `category` slot
   text against the ES `taxonomy` index (keyword + fuzzy match on names) to
   `category_id`/`subcategory_id` filters on the search — ids are the grouping key
   everywhere (ADR-003), never names. Subcategory drilldown answers ("hvor meget på
   restauranter under Mad?") come free from the denormalized transaction fields.
4. **ML leverage (existing ML-02/ML-13/ML-15, no new IDs)**: `/analytics/top-merchants`
   + `description.raw` term aggs give merchant-memory lookups (ML-02) and cross-user
   merchant priors (ML-15) without new infra; a `dense_vector` on the `taxonomy` index
   gives zero-shot subcategory matching (ML-13). Noted in those items' context.
5. **Not proposed**: moving taxonomy *ownership* or gateway `categories`/`subcategories`
   GraphQL reads to ES — categorization-service stays the single writer/authority
   (ADR-003); ES holds read-copies only.

## Outcome (fill in when done)

_(pending)_
