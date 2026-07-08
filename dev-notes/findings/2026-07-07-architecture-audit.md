---
title: Full-codebase architecture & quality audit
date: 2026-07-07
severity: CRITICAL
area: cross-cutting
status: in-progress
resolved-by: Phase 1 (P1 backlog) 2026-07-07 — all 10 CRITICAL + H3/H4/H6/H14 resolved; see backlog
---

# Architecture audit 2026-07-07 — consolidated findings

> **Progress (2026-07-07):** Phase 1 complete. **Resolved**: C1–C10 (all CRITICAL), H3, H4, H6, H14, and the saga side of M6. Fixes are in the working tree with regression tests (not yet committed). See [backlog/BACKLOG.md](../backlog/BACKLOG.md) P1 section and [sessions/2026-07-07-phase1-p1-fixes.md](../sessions/2026-07-07-phase1-p1-fixes.md). Everything below is the original audit text; resolved items are tagged inline with ✅.

Method: 8 parallel deep-dive reviews (user+shared, transaction, categorization+ai, account/budget/goal, banking+saga, gateway+stubs, frontend, infra+cross-cutting). All findings verified against source with file:line evidence. Functionality-preserving fixes only.

Statuses live per finding ID below (`open` unless marked). Backlog items reference these IDs — see [backlog/BACKLOG.md](../backlog/BACKLOG.md).

**Counts**: 10 CRITICAL · 27 HIGH · ~45 MEDIUM · ~40 LOW.

---

## CRITICAL

**C1 — Budget month-close fabricates money on upstream failure** ✅ RESOLVED (P1-01) · budget-service
`app/adapters/outbound/transaction_port.py:34-43` returns `{}` on any HTTP error → `monthly_budget_service.py:270-279` computes `spent=0`, closes the month irreversibly and emits the **entire budget as surplus**, which goal-service credits to savings. `source_key` dedup makes replay impossible. *Fix: TransactionPort raises; `close_month` → 503; never close on error.*

**C2 — IDOR: entire monthly-budgets API** ✅ RESOLVED (P1-02) · budget-service
`monthly_budget_api.py` — every endpoint takes `account_id` as query param, JWT identity discarded (`_user_id`); any authenticated user can read/modify/delete/**close** another user's budgets (close triggers the C1 money flow). *Fix: filter by `user_id` (column exists, unused) or verify ownership like goal-service does.*

**C3 — IDOR: bank disconnect + connection listing** ✅ RESOLVED (P1-03) · banking-service
`bank_api.py:226-234` + `service.py:226-250`: disconnect never checks ownership → any user can revoke any user's EB session. `bank_api.py:186-192` + `service.py:161-175`: connection listing leaks other users' bank names/IBANs. `sync` has the check; these two don't. *Fix: apply the existing `_verify_account_access` pattern.*

**C4 — Unauthenticated saga status API leaks bank transactions** ✅ RESOLVED (P1-04) · saga-service
`app/main.py:24-53`: `GET /api/v1/sagas/{id}` — no auth, returns full `context` including `fetched_items` (all synced transactions). Only defense is UUID guessability; CORS opened to frontend. *Fix: JWT + `context.user_id` check + status-only projection (gateway proxy `saga_api.py` already does the ownership check — make saga-service match or bind it to internal network only).*

**C5 — Unbounded full-history fetch on every dashboard read** ✅ RESOLVED (P1-07) · gateway + transaction-service
`gateway/transaction_client.py:33-40` sends no date/limit params; tx-service `find_by_account` has no LIMIT (`postgres_transaction_repository.py:74-84`) and its filter dispatch ignores date ranges when `account_id` is set (`service.py:161-168`). Every dashboard/GraphQL read downloads the account's entire history; `currentMonthOverview` does it **twice**, sequentially, plus taxonomy twice. Grows linearly forever. *Fix: pass date range + pagination through; fix tx-service filter combination; memoize per request.*

**C6 — Fail-open JWT verification (empty-string secret)** ✅ RESOLVED (P1-06) · gateway + ai-service
`gateway/config.py:23` and `ai-service/config.py:20` default the secret to `""` — a missing env var means tokens signed with `""` verify. Other services correctly crash at startup. *Fix: required setting, fail fast.*

**C7 — AI ingest blocks the event loop** ✅ RESOLVED (P1-09) · ai-service
`ingest_service.py:100-135`: sync Ollama embed calls + Chroma upsert directly in async handler — one ingest freezes every concurrent SSE chat stream. Dispatcher already shows the correct `anyio.to_thread` pattern. *Fix: run batch loop in worker thread / AsyncClient.*

**C8 — Production Enable Banking private key in repo working tree** ✅ MITIGATED (P1-08: parameterized, gitignored; move key off-repo operationally) · repo root
`enablebanking-privat.pem` (+ sandbox) at repo root; gitignored and never committed (verified), but bind-mounted via compose and one `.gitignore` edit from leaking. *Fix: move outside repo / secrets manager; absolute path via env.*

**C9 — Real personal financial data committed to git** ✅ RESOLVED (P1-08: untracked + gitignored; history rewrite pending user decision) · scripts/backups
`scripts/backups/pg_deleted_dupes_20260514_123741.jsonl` — 203 real transactions (names, amounts, dates) **tracked in git**. GDPR problem; survives deletion without history rewrite. *Fix: remove + gitignore `scripts/backups/`; filter-repo if repo is ever shared.*

**C10 — One user's ingest can delete every user's vectors** ✅ RESOLVED (P1-10) · ai-service
`ingest_service.py:104-115`: embedding-dimension mismatch → drops the entire shared `transactions` collection mid-request; all tenants lose chat data until manual re-ingest. *Fix: version collection name by embedding model.*

---

## HIGH

### Security / correctness

- **H1** user-service: sync bcrypt (~250ms) inside async handlers blocks the event loop for all traffic (`app/auth.py:17-26` via `service.py:55,95`). Wrap in `to_thread`.
- **H2** Platform-wide symmetric `JWT_SECRET` (HS256): any service can mint tokens for any user — budget-service actually does (`budget-service/app/auth.py:14-22` forges arbitrary-user tokens for S2S calls). Plan RS256 (user-service holds private key); replace S2S-by-forged-user-JWT with real service credentials.
- **H3** ✅ RESOLVED (P1-05, auth added; ownership-scoping still open) — account-service: `/api/v1/account-groups` had **no auth on any route** (`account_group_api.py`); anonymous list leaks usernames.
- **H4** ✅ RESOLVED (P1-11) — account-service: `user.created` consumer dropped messages permanently on failure — `message.process()` requeue=False, no DLQ (`account_creation_consumer.py:77-94`); user never gets a default account. Copy goal-service's DLQ pattern.
- **H5** goal-service: goal events publish `account_id` in the contract's `user_id` field (`service.py:59,93,118`) — wrong identity to all downstream consumers.
- **H6** ✅ RESOLVED (P1-12) — transaction-service: saga rollback swallowed per-id failures and always replies success; docstring says soft-delete but rows are hard-deleted (`saga_command_consumer.py:139-156`). Orphan rows while saga believes it rolled back.
- **H7** saga-service: timeout worker flips sagas to `timed_out` with **no compensation** (`orchestrator.py:144-159`) — imported transactions stranded; also kills `compensating` sagas mid-rollback (`postgres_saga_repository.py:83`); late replies dropped.
- **H8** saga-service: no `FOR UPDATE`/version on saga rows — blind overwrite races between reply consumer and timeout worker; safe only at single replica + prefetch 1 (`postgres_saga_repository.py:53-126`).
- **H9** banking-service: consent `valid_until` never persisted (`expires_at` always NULL, `is_expired` dead) — after 90 days syncs fail deep in the saga with opaque errors instead of a "reconsent needed" 409.
- **H10** banking-service: EB transaction identity (`entry_reference`) and `currency` dropped before import (`saga_command_consumer.py:127-135`) — re-sync dedup relies on fuzzy `(date, amount, description)`; identical same-day purchases wrongly deduped, description drift duplicates.
- **H11** k8s: plaintext committed secrets incl. real EB app id (`k8s/secrets.yaml`, compose line 2, KEDA secret, postgres passwords inline, Grafana admin/admin).
- **H12** infra: e2e CI can pass green with **all tests skipped** (conftest skips when health checks fail; gitignored PEM bind-mount breaks banking-service in CI invisibly).

### Performance / scalability

- **H13** gateway: all 5 HTTP clients are sync, new `httpx.Client` per call, sequential; threadpool (~40) saturates and head-of-line blocks incl. `/health`. Shared AsyncClient + `asyncio.gather`.
- **H14** ✅ RESOLVED (P1-07) — transaction-service: unbounded list queries + broken pagination — filter branches are mutually exclusive `elif`s, `skip/limit` only on the no-filter branch, `transaction_type` filtered in memory (`service.py:159-173`, repo `74-109`).
- **H15** transaction-service: N+1 dedup SELECT per row on CSV/bulk import, no composite index on the dedup key, no in-batch dupe detection, no unique-constraint backstop against concurrent imports (`service.py:300-311,377-389`).
- **H16** banking-service: sync `httpx.Client` for EB called from async handlers and the async consumer — unbounded pagination can block minutes, starving aio_pika heartbeats → redelivery loops (`enable_banking_client.py:70,218-239`).
- **H17** saga-service: full transaction list shuttled through saga context, re-serialized to `context_json` on every update and copied into command payloads — multi-MB rows/messages (`bank_sync_saga.py:54,83`).

### Maintainability / architecture

- **H18** Copy-paste infrastructure: outbox worker ×8 (7 near-identical, 3–12 lines drift; account a divergent rewrite), rabbitmq publisher ×7 (2 byte-identical), `app/auth.py` ×9 + dead `shared/auth/jwt_utils.py` (0 importers), alembic env ×7, Dockerfile template ×7, inline logging ×20 workers, `budget_period.py` ×3 byte-identical (gateway/budget/account). Extract to `services/shared/` (contracts package proves the mechanism, 43 importers).
- **H19** categorization-service: the rules DB is dead — engine builds from hardcoded `SEED_MERCHANT_MAPPINGS` (`taxonomy.py`), migration-seeded `categorization_rules` + full `PostgresRuleRepository` never feed it; provider docstring claims DB reload (false). DB edits have zero effect.
- **H20** categorization-service: consumer re-implements the tier pipeline inline, bypassing `CategorizationService`, and builds its engine once at startup (no TTL) — new subcategories need a consumer restart (`transaction_consumer.py:215-225,302-321`).
- **H21** ai-service compose drift: `LLM_MODEL` is a dead key; responder defaults `qwen3:8b` which `ollama-pull` never pulls → responder 404s on fresh host; `OLLAMA_BASE_URL` points at host Ollama while compose pulls 5 GB into an unused container.
- **H22** frontend: JWT + identity in localStorage, no expiry decoding — expired token shows logged-in UI until first 401 hard-redirect.
- **H23** frontend: 3,534-line dead hexagonal `components/Budget/` module (+ dead `api/budgets.jsx`, `CSVUpload/`, `PrivateRoute.jsx`) — zero importers, misleads on house style.
- **H24** frontend: login 403 fallback is an empty placeholder → navigate to a guarded route without a token → silent bounce back to login (`LoginPage.jsx:30-35`).
- **H25** frontend: goals fetched 3 independent ways (react-query + 2 local fetches) coordinated by a `refreshTrigger` counter prop; caches disagree.
- **H26** account-service: repo makes 1 sync HTTP call per user per group (`postgresql_account_group_repository.py:83-94`) — up to 100×N sequential 5s-timeout calls per list; I/O from persistence layer.
- **H27** CI: matrix omits categorization/banking/saga services (their tests run nowhere); bandit `|| true` can never fail; root `make test` covers 6 of 11 services.

---

## MEDIUM (grouped)

**Messaging hygiene** (pattern repeated in tx-service, categorization, goal, saga, banking):
- M1 Retry-republish goes through the shared topic exchange with the original routing key — every future subscriber gets up to 3 duplicate deliveries per failure. Publish to own queue via default exchange or TTL retry queue. (5 sites.)
- M2 `json.loads` outside try/except in consumers → poison message never acked, redelivered forever, wedges prefetch=1 queues (`transaction saga_command_consumer.py:66`, `categorized_consumer.py:83`, `categorization transaction_consumer.py:107`).
- M3 prefetch=1 + inline `asyncio.sleep(2**retry)` (up to 16s) = head-of-line blocking during bulk imports (`categorized_consumer.py:126-137`).
- M4 Outbox workers hold `FOR UPDATE` locks across up to 20 broker round-trips, commit per batch (crash → batch republish); no max-attempts dead state; no purge of published rows (unbounded growth) — all 8 copies.
- M5 Outbox worker loops have no try/except → transient DB error kills process, relying on container restart (user-service et al.).
- M6 Saga: compensation reply outcome ignored (no success param) — failed rollback marked COMPENSATED (`orchestrator.py:119-142`); start consumer hardcodes bank_sync field extraction; typed saga contracts in shared/contracts unused and already drifted.
- M7 Banking projection idempotency keyed on `correlation_id` instead of an event id — works by accident (`account_projection_consumer.py:90-106`). Add `event_id` to `BaseEvent`.
- M8 No dedup/serialization of concurrent bank-sync sagas per connection — double-click → two concurrent imports racing the dedup heuristic.

**Broken caching**:
- M9 tx-service list cache + budget summary cache: fastapi-cache2 default key includes `repr(service instance)` → keys nondeterministic, near-zero hits; on address reuse serves stale data never invalidated by writes (`transaction rest_api.py:53`, `budget monthly_budget_api.py:43-52`).
- M10 Redis URLs hardcoded (`transaction main.py:29`, `budget main.py:32`), clients never closed; breaks k8s deploys.
- M11 Gateway: zero caching of slow-changing taxonomy; per-request ownership check is an uncached HTTP round trip; missing `X-Account-ID` silently falls back to "first account".

**Fail-open / auth consistency**:
- M12 budget `CategoryPort.exists()` fails open (like C1's port).
- M13 categorization `/categorize` endpoints unauthenticated on a published port.
- M14 tx-service `/bulk` documented "internal" but exposed with plain user JWT; caller-supplied `categorization_tier="manual"` shields rows from auto-categorization; `account_id` never ownership-checked anywhere in the service.
- M15 Gateway auth failures return 400/GraphQL-200 instead of 401; REST dashboard has no exception mapping (upstream failures → 500).
- M16 banking/goal `INTERNAL_API_KEY` defaults to the known dev string in code; saga `DATABASE_URL` defaults to in-memory SQLite (4 workers silently get private empty DBs).
- M17 ai-service forwards client-supplied `X-Account-ID` downstream unverified.

**Data / correctness**:
- M18 Naive `datetime.utcnow()` vs DB `now()` mixing (banking pending-auth expiry ±TZ; ≥5 files repo-wide).
- M19 EB amounts parsed to `float` (`enable_banking_client.py:284`).
- M20 tx-service: `TransactionCreatedEvent` construction copy-pasted 3× in service; saga item `description` defaults `""` vs `None` elsewhere → dedup misses; absent tier/confidence overwrite with `""`.
- M21 budget-service: two parallel budget domains (`budgets` vs `monthly_budgets`) with no sync.
- M22 goal balance read-modify-write without lock (single-replica-safe only).
- M23 account-service: sync stack + psycopg2/asyncpg driver split across processes of one service; repo-level commits vs injected `commit_fn` vs dead `SyncUnitOfWork` (three transaction disciplines).
- M24 ai-service: `amount_min` clobbers `amount_max` in filters; router prompt never emits those slots (unreachable code); ports decorative with drifted signatures; ChromaDB manual full re-ingest only (ghost data for deleted transactions; embedded client = 1 replica max).
- M25 gateway `AnalyticsService` name collides with the analytics-service stub; real analytics logic lives in gateway.

**Frontend**:
- M26 Cache-invalidation gaps between transactions/dashboard/periodOverview keys → stale cross-page data; `forceRefresh` uses sleep(2500) double-invalidate.
- M27 Currency/date formatting duplicated 6+ ways, visibly inconsistent ("1234.56 DKK" vs "1.234,56 kr."); snake_case/camelCase dual shapes leak into components; `account.idAccount || account.id` repeated.
- M28 No pagination/virtualization on the transactions table; notification setters prop-drilled parallel to existing context; `account_id` read from localStorage during render (non-reactive query keys).

**Infra**:
- M29 Compose: no healthchecks/restart policies on API services; `account-outbox-publisher` has NO restart policy (dies silently → event delivery halts); `depends_on: service_started` everywhere.
- M30 k8s: 2 of ~50 Deployments have resource requests (HPAs only work on those two); no probes on 19 workers; redis/monitoring on emptyDir (data loss); ollama unpinned.
- M31 Monitoring: saga-service missing from Prometheus targets; 2 alert rules total; configs duplicated compose↔k8s.
- M32 `processed_events` tables never pruned (index exists, no job).
- M33 committed `services/categorization-service/.env` (tracked despite gitignore) and `services/user-service/.env` with dev secrets.

---

## LOW (condensed)

- user-service: register check-then-insert race → 500 (should be 409); worker bypasses `IEventPublisher` port (`publish()` dead); bcrypt char-vs-byte truncation; username with `@` can register but never log in; login timing side channel; migrations at container start race >1 replica; `event_type` overridable and doubles as routing key; contracts README stale.
- transaction-service: consumers import ORM directly while saga consumer uses UoW (two architectures); `list_planned` skips UoW; per-row `session.refresh` after bulk insert; CSV `UnicodeDecodeError` → 500; `BulkCreateTransactionItemDTO` field-for-field copy; code-before-imports smell (also in user-service).
- saga/banking: `find_stale` N+1 + full context deserialization; unbounded EB pagination loop; saga PK externally supplied (non-UUID → generic DLQ path); `get_active_by_uid` MultipleResultsFound on historical dupes; plaintext EB `session_id` at rest (bearer credential).
- gateway: GraphiQL + introspection on by default, no depth limits; `int(saga_user_id)` can 500; no `require_exp` on JWT decode; Dockerfile as root, no healthcheck.
- ai/categorization: `RETRIEVAL_TOP_K` never read; deprecated `on_event`; missing-"Anden" degrades to `category_id=0` silently; throwaway sample embedding per ingest; `total_tokens` counts chunks; broken `scripts/sanity_check_retrieval.py` (imports deleted module); `test_chromadb_sanity*/` binary vector DBs in tree.
- account/budget/goal: unpinned account requirements.txt; `GET /monthly-budgets/` returns `200 null`; redundant double HTTP on goal create; account-service hand-rolls event JSON instead of contracts.
- frontend: never-resolving Promise on 401 leaves hung `finally`s; DOM query to reset file input; chat retry can send `''`; `useCallback` deps defeated; committed `build/` output; `rag_ingested` flag global not per-account; API modules named `.jsx`.
- repo hygiene: root `node_modules/` + stray `package-lock.json` (accidental `npm install recharts`); empty `dumps/`; `services/monolith/` = untracked debris only (delete); `metrics-patch.json` loose at root; ADR numbering schemes collide (`docs/adr/000N` vs `docs/ADR-00N`); `goal-service-ci.yml` self-described as redundant; `sleep 30` in CI vs `--wait` in script; pyright scoped to 1 service.

---

## Positives worth preserving

Transactional outbox UoW (user-service exemplar), SKIP LOCKED horizontal scalability, inbox dedup + `source_key` design (goal-service consumer is the reference), ADR-003 taxonomy read-copies, atomic single-use OAuth state, saga orchestrator's transactional advance, callback error→redirect mapping, graceful-degrade categorization client, frontend chat slice + crudFactory + query-key factories, honest stub READMEs, AsyncAPI event documentation.
