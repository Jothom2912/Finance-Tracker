# Backlog

Prioritized work queue. IDs are stable — never renumber. Effort: S (<½ day), M (1–2 days), L (multi-day).
Finding IDs (C/H/M/L…) refer to [findings/2026-07-07-architecture-audit.md](../findings/2026-07-07-architecture-audit.md).
Execution strategy: [plans/2026-07-07-refactoring-roadmap.md](../plans/2026-07-07-refactoring-roadmap.md).

**How to read this file.** The three tables are the whole queue — read them and stop.
Rows that needed more than a sentence link to `[→ detail](#p1-13)`; those sections live
under [Item details](#item-details) at the bottom and are addressable by ID, so
`grep -n '### P2-26' BACKLOG.md` lands directly on one. Keep new rows to one line: a
description that outgrows its cell goes in a detail section, and a *completion report*
goes in the shipping plan's **Outcome** section and the session log, not here.

## P1 — Critical (security holes, money-corruption, data loss)

**Phase 1 COMPLETE (2026-07-07)** — all items implemented with regression tests, verified green per service; since committed to master (e.g. saga auth/rollback in 3d64643b). See [sessions/2026-07-07-phase1-p1-fixes.md](../sessions/2026-07-07-phase1-p1-fixes.md). Two deploy actions required (see session log): delete+recreate the `account_service.account_creation` RabbitMQ queue (new DLQ args), and users must re-ingest AI vectors once (versioned collection).

> **P1-13 added 2026-07-25, after the phase was declared complete.** Filed here rather than in P2 because this table's admission rule is *money-corruption*, and the rule is about the defect's class, not the date it was found. The phase header above stays accurate for the 2026-07-07 audit; P1 is not "closed" as a category.

| ID | Title | Area | Effort | Status | Links |
|----|-------|------|--------|--------|-------|
| P1-01 | Fail-closed month close: TransactionPort raises, close_month → 503 on upstream error | budget | S | done | C1, M12 |
| P1-02 | Ownership checks on all monthly-budget endpoints (use existing `user_id` column) | budget | S | done | C2 |
| P1-03 | Ownership checks on bank disconnect + connection listing (reuse `_verify_account_access`) | banking | S | done | C3 |
| P1-04 | Authenticate saga status API (JWT + user check, or internal-only + gateway proxy); strip `fetched_items` from responses | saga | S | done | C4 |
| P1-05 | Auth dependency on account-groups routes | account | S | done | H3 |
| P1-06 | Remove empty-string JWT secret defaults (gateway, ai); fail fast at startup in all services | gateway, ai | S | done | C6 |
| P1-07 | Date-range + pagination through gateway→tx-service; fix tx filter combination (single query builder, all filters + OFFSET/LIMIT in SQL) | gateway, transaction | M | done | C5, H14 |
| P1-08 | Move EB PEM keys out of repo; purge committed personal data (`scripts/backups/*.jsonl`) + gitignore; `git rm --cached` tracked `.env` files | repo | S | done | C8, C9, M33 |
| P1-09 | AI ingest off the event loop (`anyio.to_thread` / AsyncClient) | ai | S | done | C7 |
| P1-10 | Version ChromaDB collection by embedding model (stop full-collection wipe) | ai | S | done | C10 |
| P1-11 | DLQ/requeue for account-service `user.created` consumer (copy goal-service pattern) | account | S | done | H4 |
| P1-12 | Saga rollback honesty: collect per-id failures, reply `success:false`; honor compensation reply outcome in orchestrator | transaction, saga | M | done | H6, M6 |
| P1-13 | budget-service computes spend from at most 50 transactions. [→ detail](#p1-13) | budget, transaction | M | **done 2026-07-25** | [findings/2026-07-25-budget-spend-truncated-at-50.md](../findings/2026-07-25-budget-spend-truncated-at-50.md), [plan](../plans/2026-07-25-p113-budget-spend-from-analytics.md), [decision](../decisions/2026-07-25-budget-spend-from-analytics.md) |
| P1-14 | The transactions page silently shows only the 50 newest rows in the selected period. [→ detail](#p1-14) | frontend, transaction | M | **done 2026-07-26** | [findings/2026-07-26-transaction-list-truncated-at-50.md](../findings/2026-07-26-transaction-list-truncated-at-50.md), [plan](../plans/2026-07-26-p114-transaction-list-pagination.md), [decision](../decisions/2026-07-26-transaction-list-envelope.md) |
| P1-15 | `/api/v1/categorize` is unauthenticated and reads `user_id` from the request body. [→ detail](#p1-15) | categorization, repo | S | **done 2026-07-27** | [findings/2026-07-26-categorize-endpoint-unauthenticated.md](../findings/2026-07-26-categorize-endpoint-unauthenticated.md), [sweep SEC-1](../findings/2026-07-26-product-surface-sweep.md) |
| P1-16 | `graphql-request` afviser den relative URL P3-43 gav den, så hele GraphQL-læsestien er død i browseren. [→ detail](#p1-16) | frontend | S | **done 2026-07-28** | [finding](../findings/2026-07-28-graphql-client-rejects-relative-url.md), [plan](../plans/2026-07-28-p325-p227-perimeter-headers-ratelimit.md#outcome) |

> **P1-14 and P1-15 added 2026-07-26** from the [product-surface sweep](../findings/2026-07-26-product-surface-sweep.md), under the same admission rule P1-13 invoked: the class of the defect decides the tier, not the date it was found. P1-14 is money-presentation (an incomplete set of financial records shown as complete); P1-15 is a security hole (unauthenticated cross-user data disclosure, verified live).

> Partial-scope carry-overs from Phase 1 (added to P2/P3 tracking):
> - P1-08 left `.env` files still tracked (`services/{budget,categorization,saga}-service/example.env` are examples and fine; the real tracked `.env` risk is covered by `**/.env` gitignore — none currently tracked). Git history rewrite for the purged PII backup is **still pending a user decision**. ⚠️ **The condition it was deferred on is met**: it was filed as "only needed if the repo is ever shared", and `origin` is **public** (`github.com/Jothom2912/Finance-Tracker` — confirmed 2026-07-26 by an anonymous API read returning 200). The purged personal data is therefore reachable in history by anyone, and has been for as long as it was committed. Deliberately **not** acted on unilaterally: a history rewrite on a published repo invalidates every clone and cannot be undone. Needs an explicit decision on rewrite-vs-accept, and note that force-pushing does not evict data already fetched or cached by GitHub — treat the values as disclosed and rotate anything credential-shaped regardless of which option is chosen.
> - P1-02: budget `create` still relies on the `(account_id, month, year)` unique constraint (not user-scoped) — a cross-user create for the same account/period would 500. Accounts are single-owner so it's latent; noted under M21/P3-03 area.
> - P1-05: account-groups are authenticated but not ownership-scoped (no owner column) — remains a known limitation; candidate new backlog item if group data becomes sensitive.

## P2 — Important (systemic debt, perf, at-least-once hygiene)

**Phase 2 code-COMPLETE (updated 2026-07-16)** — wave-B adoption done 2026-07-15, P2-09 shipped 2026-07-16 ([sessions/2026-07-16-p209-external-id-currency.md](../sessions/2026-07-16-p209-external-id-currency.md)). Only P2-15 (k8s secrets, pure infra) remains. (Historical surveys: [sessions/2026-07-15-phase2-wave-b-resume.md](../sessions/2026-07-15-phase2-wave-b-resume.md), [sessions/2026-07-07-phase2-in-flight.md](../sessions/2026-07-07-phase2-in-flight.md).)

| ID | Title | Area | Effort | Status | Links |
|----|-------|------|--------|--------|-------|
| P2-01 | Extract `services/shared/messaging` (outbox worker, outbox repo, rabbitmq publisher, consumer base with DLQ+delayed retry) — migrate all 8 services | cross | L | **done 2026-07-15** — all 8 outbox services on the shared package | H18, M1–M5 |
| P2-02 | Extract `services/shared/auth` (real package; replace 9 copies; kill dead `jwt_utils.py`; `require_exp`) | cross | M | **done 2026-07-15** — all 10 services on the shared package; dead jwt_utils deleted earlier; token *minting* stays local in user/budget/account by design | H18, M4 (gateway L6) |
| P2-03 | Move `budget_period.py` to shared (3 byte-identical copies) | cross | S | **done 2026-07-15** — gateway, budget, account, analytics all import from finans-tracker-domain; analytics keeps only its two analytics-specific extensions locally | H18 |
| P2-04 | Gateway async rewrite: shared AsyncClient per upstream, `asyncio.gather` for independent calls, per-request memoization of tx/taxonomy fetches, retry+breaker helper | gateway | M | partially done, rest deliberately rolled back (2026-07-12): memoization shipped; the async conversion was reverted to sync because master's ADR-0004 analytics stack is sync and the legacy read path is slated for post-cutover deletion — redo async (if still needed) after that cleanup. Legacy-stien slettet 2026-07-13 (session-log): full-history-fetch + memoization-fundene bortfaldt; async kun ved målt behov | H13, H1/H2-gw, M11 |
| P2-05 | Import dedup: batch anti-join query + composite index + in-batch set + unique partial index backstop | transaction | M | done (committed e778990b: batch anti-join, in-batch seen-set, migration 011) | H15 |
| P2-06 | Wire rules DB into rule engine; consumer uses `CategorizationService` + shared provider (TTL) | categorization | M | done (2026-07-12: `main()`/`_categorize` were left half-migrated → NameError crash-loop; finished the provider wiring, verified live + 51 unit tests) | H19, H20 |
| P2-07 | Async EB client (`httpx.AsyncClient`); page caps; Decimal amounts | banking | M | done (committed 31ae3b6a) | H16, L, M19 |
| P2-08 | Persist consent `valid_until`; gate sync on expiry → 409 "reconsent needed" | banking | S | done (committed 31ae3b6a) | H9 |
| P2-09 | Carry `entry_reference` + `currency` through saga import; dedupe on `(account_id, external_id)` | banking, transaction | M | **done 2026-07-16** | H10 |
| P2-10 | Saga robustness: `FOR UPDATE` on saga rows; timeout → compensation (not abandonment); don't timeout `compensating` (scoped: H17 staging deferred) | saga | L | done (committed 3d64643b, with new lock/status-API tests) | H7, H8 |
| P2-11 | Sync bcrypt → thread offload; catch IntegrityError → 409 on register | user | S | done (2026-07-15: unit 32p + integration 16p green; conftest bug fixed in fee7a5ea) | H1, L |
| P2-12 | Fix broken response caches (delete them); Redis URL from settings, close on shutdown | transaction, budget | S | done (committed c8a20088) | M9, M10 |
| P2-13 | Fix goal event `user_id` (pass resolved owner) | goal | S | done (agent reported green) | H5 |
| P2-14 | CI: add categorization/banking/saga to matrix; un-neuter bandit; fail e2e job when tests skipped; align root Makefile | infra | S | done (committed 02d1dba6: matrix +4 services, bandit -ll -ii hard-fail, e2e health-gate + CI abort-on-unreachable, root Makefile PY_SERVICE_DIRS) | H12, H27 |
| P2-15 | k8s secrets via secretGenerator/SOPS. **Correction 2026-07-27: drop the "remove real EB app id" clause** — the tracked id is the *sandbox* id and is deliberately an interpolation default (`docker-compose.yml`), the PEMs are gitignored, and the production id already lives only in untracked `.env` | infra | M | open (deferred) | H11 |
| P2-16 | Compose hardening: healthchecks + restart policies on APIs, restart for account-outbox-publisher, `depends_on: service_healthy`; fix ai-service Ollama drift (models + base URL) | infra | S | done (committed 0a4b50e2, live-verified full stack green) | M29, H21 |
| P2-17 | Frontend: delete dead Budget module + dead files; JWT `exp` check at bootstrap; fix login 403 fallback | frontend | S | done (committed 4ffb32b9) | H22–H24 |
| P2-18 | Frontend: single `useGoals()` hook; centralized invalidation helper for all financial query keys; drop refreshTrigger + sleep-based forceRefresh | frontend | M | done (committed 4ffb32b9 + 23f6c6bd) | H25, M26 |
| P2-19 | Consumer hygiene sweep (with P2-01): parse inside try, retries to own queue, prefetch >1 where idempotent, no inline sleeps | cross | M | done 2026-07-15 via P2-01 adoption: parse-inside-try everywhere, retries to own queue | M1–M3 |
| P2-20 | Outbox lifecycle: per-entry commit, max-attempts dead state, purge published rows + prune `processed_events` | cross | M | done 2026-07-15 via P2-01 adoption: shared worker defaults to per-entry commit; max-attempts dead-state + purge available (opt-in per service, not yet enabled anywhere) | M4, M32 |
| P2-21 | k8s manifest drift: 6 workloads + 1 DB live in compose but have no manifest or `kustomization.yaml` entry. [→ detail](#p2-21) | infra | M | open | [findings/2026-07-25-k8s-manifest-drift.md](../findings/2026-07-25-k8s-manifest-drift.md) |
| P2-22 | Inbox guard on banking's saga-command consumer. [→ detail](#p2-22) | banking | S | **done 2026-07-25** | [plan](../plans/2026-07-25-p222-saga-inbox-and-loose-ends.md) |
| P2-23 | Stored reply for transaction-service's `bulk_import` saga command. [→ detail](#p2-23) | transaction, banking | M | open | [plan](../plans/2026-07-25-p222-saga-inbox-and-loose-ends.md) (step 3) |
| P2-25 | Transaction soft-delete decision + gone-vs-not-yet in the categorization write-back. [→ detail](#p2-25) | transaction | M | **done 2026-07-28** | [decision](../decisions/2026-07-28-transaction-soft-delete.md), [plan](../plans/2026-07-28-p225-transaction-soft-delete.md) |
| P2-24 | Shared internal-API client in `services/shared`. [→ detail](#p2-24) | cross | M | open | [plan](../plans/2026-07-25-notification-service-hardening.md) (not-fixed list) |
| P2-26 | Turn on `require_exp` in all 12 services. [→ detail](#p2-26) | cross | S | **done 2026-07-27** | [sweep SEC-2](../findings/2026-07-26-product-surface-sweep.md) |
| P2-27 | No rate limiting anywhere — **oplåst af P3-43**: `limit_req`-zone i nginx.conf frem for `slowapi` i N services. [→ detail](#p2-27) | user, cross | S | **done 2026-07-28** | [plan](../plans/2026-07-28-p325-p227-perimeter-headers-ratelimit.md), [sweep SEC-4](../findings/2026-07-26-product-surface-sweep.md), [ADR-0005](../../docs/adr/0005-nginx-as-security-perimeter.md) |
| P2-28 | Any authenticated user can mutate or delete the global taxonomy. [→ detail](#p2-28) | categorization | M | open | [sweep SEC-5](../findings/2026-07-26-product-surface-sweep.md) |
| P2-29 | CSV upload has no size limit, no MIME check and buffers the whole file. [→ detail](#p2-29) | transaction | S | done 2026-07-28 | [sweep SEC-7](../findings/2026-07-26-product-surface-sweep.md), [plan](../plans/2026-07-28-p229-csv-upload-guards.md) |
| P2-32 | Outbox-porten erklærer domænets `OutboxEntry`, men adapteren tilskriver shared's klasse af samme navn — usand kontrakt i 7 services; fix er en mapping i adapteren, ikke en sletning af duplikatet (det er den hexagonale grænse) | cross, contracts | S | open | [findings/2026-07-27-outbox-port-declares-foreign-entity.md](../findings/2026-07-27-outbox-port-declares-foreign-entity.md) |
| P2-37 | **Én install-sti per service.** `requirements.txt` og `uv.lock` er to sandhedskilder i én service — budget — hvor det lod en grøn gate udstede en container der døde ved import. [→ detail](#p2-37) | cross, CI, deps | S | done 2026-07-28 | [plan + Outcome](../plans/2026-07-28-p237-budget-single-install-path.md#outcome) · [finding](../findings/2026-07-27-none-annotation-204-fastapi-split.md) |
| P2-39 | **Browser-automatisering som ejet instrument.** Nul browser-lag i repoet, og begge eksisterende suiter var grønne gennem hele P1-16. [→ detail](#p2-39) | frontend, test, CI | M | **done 2026-07-28** | [plan + Outcome](../plans/2026-07-28-p239-browser-automation.md#outcome) · [decision](../decisions/2026-07-28-browser-automation-instrument.md) |
| P2-40 | **Gateway'ens `accounts[0]`-fallback: vælg eksplicit eller fejl ærligt.** Uden `X-Account-ID` fik en flerkonto-bruger en anden kontos data uden en fejl. [→ detail](#p2-40) | gateway, account, test | S | **done 2026-07-29** | [plan + Outcome](../plans/2026-07-28-p240-gateway-explicit-account-resolution.md#outcome) · [finding](../findings/2026-07-28-gateway-falls-back-to-first-account.md) |
| P2-41 | Hverken account- eller user-service eksponerer DELETE, og `Account` har ingen `is_deleted`-kolonne — soft-delete-konventionen er fraværende for de to entiteter der ejer alt andet. Ingen GDPR-sti, og dev-stakken kan kun ryddes med `down -v`. DB-sletning er udelukket: `Account` er projiceret i tre services | account, user, domain | M | open | [findings/2026-07-28-no-delete-path-for-account-or-user.md](../findings/2026-07-28-no-delete-path-for-account-or-user.md) |
| P2-42 | **a-halvdel done 2026-07-29:** `BankConfigError` → 503 + WARNING (app-level handler, fordi fejlen kastes under dependency-resolution og ingen rute-`try/except` kan nå den), plus en gate der fanger døde/restartende containere — den klasse `Wait for system` strukturelt ikke kan se, da 26 workers ingen HTTP-overflade har. **Tilbage (open):** b-halvdelen — et liveness-probe kan stadig ikke se en brudt afhængighed, hvilket var bankings faktiske fejlmode | banking, CI | S | a done, b open | [plan + Outcome](../plans/2026-07-29-p238-p242-ci-missing-signal.md#outcome) · [finding](../findings/2026-07-28-banking-service-dead-in-ci.md) |
| P2-38 | **done 2026-07-29:** `timeout-minutes` på alle 5 job-definitioner, sat efter målt varighed og verificeret rød. Negativt resultat: ES-fixturen manglede *ikke* en wait-timeout — testcontainers 4.14.2 bounder den til 120 s og fejler læsbart, og de 836 s beviser at hængen lå i det ubundne image-**pull**, som ingen fixture kan bounde. [→ detail](#p2-38) | ci, analytics | S | **done 2026-07-29** | [plan + Outcome](../plans/2026-07-29-p238-p242-ci-missing-signal.md#outcome) · [finding](../findings/2026-07-28-ci-job-can-hang-undetected.md) |
| P2-36 | `x-retry-count` læses fem steder på fire forskellige måder; `shared/messaging`, analytics ×2 og banking mangler stadig hærdning, og bankings kopi kaster `TypeError` på en `str`-header inde i retry-handleren → uendelig redelivery. Overvej at flytte transactions `retry_headers.retry_count` til shared og lade alle fem kalde den | cross, messaging | S | open | [findings/2026-07-27-retry-header-read-five-ways.md](../findings/2026-07-27-retry-header-read-five-ways.md) |
| P2-35 | `id: Optional[int]` på domain-entiteter gør persisteret og upersisteret entitet til samme type, så hver læse-sti får den svagere invariant (budget 3 entiteter, categorization 6, account 2, goal 1). Pydantic vagter de fleste kaldsteder; `mark_closed(budget.id)` gør ikke, og et `None` dér bliver `WHERE id IS NULL` → vildledende 409. Vælg mellem assert, split type (`Persisted*`) eller status quo | cross, domain | M | open | [findings/2026-07-27-optional-id-hides-unpersisted-entity.md](../findings/2026-07-27-optional-id-hides-unpersisted-entity.md) |
| P2-34 | `goal-service`: `Goal` bygges med `float` af det ene repository og `Decimal` af det andet, `Mapped[float]` mod en `Numeric`-kolonne, og forskellen lækker ud i event-payloads via `str()`; desuden `Goal.status` som magic string hvor `GoalStatus` findes. Blokerer servicen for typecheck-gaten (23 fejl, 5 ægte) | goal, domain | M | open | [findings/2026-07-27-goal-entity-two-runtime-types.md](../findings/2026-07-27-goal-entity-two-runtime-types.md) |
| P2-33 | `INTERNAL_API_KEY` er typet `str \| None = None` i 6 services men obligatorisk i mindst 3 (banking ×2, goal, notification) — beslut per service hvilket af de to legitime mønstre der gælder: påkrævet felt, eller transactions betingede header | cross, config | S | open | [findings/2026-07-27-internal-api-key-optional-but-mandatory.md](../findings/2026-07-27-internal-api-key-optional-but-mandatory.md) |
| P2-31 | mypy som hård gate. Landet på 8 af 12 services; goal/banking/account/gateway udenfor med hver sin blocker, og `tests/` er ikke dækket. [→ detail](#p2-31) | cross, CI | M | **done 2026-07-27** | [findings/2026-07-27-sync-trigger-double-value.md](../findings/2026-07-27-sync-trigger-double-value.md), [plan](../plans/2026-07-27-p231-static-typecheck-gate.md) |
| P2-30 | `test_budget_month_closed_e2e.py` closes the month before the spend it depends on has reached the read side. [→ detail](#p2-30) | budget, analytics, test | S | **done 2026-07-27** | [P1-14 verification](../plans/2026-07-26-p114-transaction-list-pagination.md), [P1-13 plan](../plans/2026-07-25-p113-budget-spend-from-analytics.md) |

## P3 — Nice-to-have (consistency, hygiene, docs)

| ID | Title | Area | Effort | Status | Links |
|----|-------|------|--------|--------|-------|
| P3-01 | account-service async migration + monolith-residue purge (dead auth/config/db code, pinned deps, non-root Docker, migrations out of API process) | account | L | open | M23, L |
| P3-02 | RS256 JWT plan + real S2S credentials (kill budget's forged user tokens) — write ADR first | cross | L | open | H2, M16 |
| P3-03 | Deprecate legacy `/api/v1/budgets` domain | budget | M | open | M21 |
| P3-04 | Event-driven ChromaDB sync (consume transaction events; handle deletes); wire or delete decorative ai ports | ai | L | **done 2026-07-14** — ports-halvdelen 2026-07-12; sync-halvdelen løst af AI-20-cutover (event-synced ES-index erstatter ChromaDB; Chroma-koden slettet 2026-07-17 efter bake, commit f03a55a4) | M24 |
| P3-05 | Batch user lookup for account groups (kill N+1 HTTP in repo) | account, user | M | open | H26 |
| P3-06 | Frontend: shared formatters everywhere; camelCase normalization at API boundary; **virtualized** tx table (the *pagination* clause left with P1-14 2026-07-26 — server-side paging shipped; virtualisation only matters once a single page is large, which 50 rows is not); accountId into AuthContext | frontend | M | open | M27, M28, [P1-14](../plans/2026-07-26-p114-transaction-list-pagination.md) |
| P3-07 | Repo hygiene: delete root node_modules/package-lock, dumps/, monolith debris, test_chromadb_sanity*, metrics-patch.json relocation, frontend build/ untracking, redundant goal-service-ci.yml | repo | S | open — ai-service-delen done 2026-07-12 (test_chromadb_sanity*/ + .pytest_cache slettet fra disk; var allerede gitignorede/utrackede; brudt sanity-script git rm'et) | L |
| P3-08 | Unify ADR numbering (migrate `docs/ADR-00N-*` into `docs/adr/` sequence) | docs | S | open | L |
| P3-09 | `event_id` on BaseEvent; projection dedup on it; freeze `event_type` per contract | contracts | M | open | M7, L |
| P3-10 | Timezone-aware timestamps everywhere (shared util in P2-01 package) | cross | M | open | M18 |
| P3-11 | Observability: `/metrics` on services or at least saga-service in Prometheus targets; worker liveness probes; resource requests baseline | infra | L | open | M30, M31 |
| P3-12 | Gateway: rename `AnalyticsService`→`DashboardReadService`; GraphiQL gated to dev; depth limits; 401 semantics; REST exception mapping | gateway | M | open | M15, M25, L |
| P3-13 | E2E coverage: bank-sync saga, categorization outcomes, ai-service smoke; health-gate all 10 services | tests | M | open | H12 |
| P3-14 | Serialize bank-sync sagas per connection (deterministic correlation id) | banking | S | **done 2026-07-17** | M8 |
| P3-15 | Bulk-import item-count limits vs saga (chunking): `BulkCreateTransactionDTO.items` is 1..500 — an EB fetch with 0 or >500 items raises ValidationError in `_handle_bulk_import` → 3 retries → saga failure. Chunk in the consumer (or relax bounds for the internal path) | transaction | S | **done 2026-07-17** (commit 2cce0a09: 0 items = success-reply without DB round-trip; >500 chunked à 500, one UoW per chunk, aggregated reply; mid-chunk crash retries idempotently via P2-09 dedup) | — |
| P3-16 | Goal delete vs allocation history: hard-delete on a goal with `goal_allocation_history` rows → FK violation → 500. Decide soft-delete (preferred, preserves audit trail) or 409-guard; ensure default-flag never points at a dead goal | goal | S | **done 2026-07-17** (commit 5cd613e5: soft-delete via `deleted_at`, migration 005; delete clears default-flag atomically; live e2e verified — [plan](../plans/2026-07-17-p316-goal-soft-delete.md)) | [findings/2026-07-17-goal-delete-fk-500.md](../findings/2026-07-17-goal-delete-fk-500.md) |
| P3-17 | Migrations as an explicit step, not an API-container side effect: 8 of 9 Dockerfiles run `alembic upgrade head` in `CMD`, and workers that override `command:` skip it. Compose hides this via `depends_on: service_healthy`; k8s has no such guarantee → worker CrashLoopBackOff until the API pod migrates. Introduce a per-service migration Job/one-shot that API and workers both wait on | infra | S | open | [findings/2026-07-25-worker-migration-ordering.md](../findings/2026-07-25-worker-migration-ordering.md) |
| P3-20 | `scripts/cleanup_pg_duplicates.py:148` deletes straight from the write DB (. [→ detail](#p3-20) | transaction, analytics, tooling | S | **done 2026-07-26** | [findings](../findings/2026-07-25-cleanup-script-desyncs-read-model.md), [plan](../plans/2026-07-26-p320-cleanup-script-outbox.md), [pattern](../patterns/transactional-outbox.md) |
| P3-22 | **CI detection: nothing surfaces a red run.** [The 2026-07-26 decision](../decisions/2026-07-26-ci-feedback-loop.md) shipped *prevention* (pre-commit hook + `repo-lint` job) but not detection — knowing CI went red required opening a browser | infra, tooling | S | **done 2026-07-26** | [decision](../decisions/2026-07-26-ci-feedback-loop.md) |
| P3-23 | **banking-service has no `pyproject.toml`** — no dev/runtime split, no lockfile, and no place to hang `[tool.mypy]`, so it could not join the gate its own bug motivated. [→ detail](#p3-23) | banking, infra | S | done 2026-07-28 | [plan](../plans/2026-07-28-p323-banking-uv-pyproject.md), [session](../sessions/2026-07-28-p323-banking-uv-pyproject.md) |
| P3-21 | ai-service's eval seed writes 66 fixture documents into the production ES index. [→ detail](#p3-21) | ai, analytics, tests | S | open | [findings/2026-07-26-eval-seed-writes-to-prod-index.md](../findings/2026-07-26-eval-seed-writes-to-prod-index.md) |
| P3-19 | Non-UUID `saga_id` retries to the DLQ instead of being rejected as poison. [→ detail](#p3-19) | saga | S | open | [findings/2026-07-25-saga-reply-non-uuid-poison.md](../findings/2026-07-25-saga-reply-non-uuid-poison.md) |
| P3-18 | notification-service lifecycle gaps: (a) no retention — rows accumulate forever, dismiss is soft-delete only, no purge job; (b) `_send_email_best_effort` fires for every notification type with no per-user preference or opt-out model, so wiring a real SMTP adapter to the existing `IEmailPort` would ship as a spam release. Decide the preferences model **before** replacing `LogEmailAdapter` | notification | S | open | [plan](../plans/2026-07-25-notification-service-hardening.md) (explicit non-goal) |

### Added 2026-07-26 from the [product-surface sweep](../findings/2026-07-26-product-surface-sweep.md)

| ID    | Title                                                                                                                                                    | Area                   | Effort                             | Status          | Links                                                                                                                                                               |
| ----- | -------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------- | ---------------------------------- | --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| P3-24 | Gateway-as-perimeter — begge halvdele lukket 2026-07-28: datastores på loopback, og ADR-0005 vælger nginx som perimeter. Implementeringen er P3-43. [→ detail](#p3-24)                         | infra, gateway         | M                                  | done 2026-07-28 | [ADR-0005](../../docs/adr/0005-nginx-as-security-perimeter.md), [decision](../decisions/2026-07-28-nginx-as-perimeter.md), [datastore-halvdel](../plans/2026-07-28-p324-datastore-loopback-bind.md#outcome)                                                                                                      |
| P3-25 | No security headers — **oplåst af P3-43**: CSP hører nu ét sted, i perimeterens `server`-blok (HSTS udeladt: ingen TLS). [→ detail](#p3-25)                                                                                            | frontend, infra        | S                                  | **done 2026-07-28** | [plan](../plans/2026-07-28-p325-p227-perimeter-headers-ratelimit.md), [sweep SEC-6](../findings/2026-07-26-product-surface-sweep.md)                                                                                                      |
| P3-26 | No dependency scanning, and banking-service pins known-vulnerable versions. [→ detail](#p3-26)                                                           | infra, banking         | S                                  | open            | [sweep SEC-8/9](../findings/2026-07-26-product-surface-sweep.md)                                                                                                    |
| P3-27 | Four containers run as root; k8s has no securityContext and no NetworkPolicy. [→ detail](#p3-27)                                                         | infra                  | M                                  | open            | [sweep SEC-10](../findings/2026-07-26-product-surface-sweep.md)                                                                                                     |
| P3-28 | Build & image hygiene — the best effort-to-payoff item in the sweep, all figures measured 2026-07-26. [→ detail](#p3-28)                                 | infra, frontend        | S                                  | open            | [sweep OPS-1](../findings/2026-07-26-product-surface-sweep.md)                                                                                                      |
| P3-29 | Compose drift left over from P2-16. [→ detail](#p3-29)                                                                                                   | infra                  | S                                  | open            | [sweep OPS-2](../findings/2026-07-26-product-surface-sweep.md)                                                                                                      |
| P3-30 | No frontend code splitting. [→ detail](#p3-30)                                                                                                           | frontend               | M                                  | open            | [sweep OPS-3](../findings/2026-07-26-product-surface-sweep.md)                                                                                                      |
| P3-31 | Gateway opens a new connection pool per upstream call. [→ detail](#p3-31)                                                                                | gateway                | S                                  | open            | [sweep OPS-4](../findings/2026-07-26-product-surface-sweep.md)                                                                                                      |
| P3-32 | Routing robustness + mobile navigation. [→ detail](#p3-32)                                                                                               | frontend               | M                                  | open            | [sweep UX-2/3](../findings/2026-07-26-product-surface-sweep.md)                                                                                                     |
| P3-33 | UI consistency: loading, errors and form validation. [→ detail](#p3-33)                                                                                  | frontend               | M                                  | open            | [sweep UX-4/5/8](../findings/2026-07-26-product-surface-sweep.md)                                                                                                   |
| P3-34 | Accessibility gaps. [→ detail](#p3-34)                                                                                                                   | frontend               | M                                  | open            | [sweep UX-6](../findings/2026-07-26-product-surface-sweep.md)                                                                                                       |
| P3-35 | The transactions page's two read paths have different scopes, and after P1-14 they share one pager. [→ detail](#p3-35)                                   | frontend, gateway      | S                                  | open            | [P1-14 non-goals](../plans/2026-07-26-p114-transaction-list-pagination.md), [decision](../decisions/2026-07-26-transaction-list-envelope.md)                        |
| P3-36 | Remove the transaction list's shape-tolerant reader once the envelope is deployed. [→ detail](#p3-36)                                                    | frontend               | XS                                 | open            | [decision](../decisions/2026-07-26-transaction-list-envelope.md), [P1-14 step 6](../plans/2026-07-26-p114-transaction-list-pagination.md)                           |
| P3-37 | `transactions` has no soft-delete column, against the repo's own convention. [→ detail](#p3-37)                                                          | transaction, analytics | M                                  | **done 2026-07-28** via P2-25 | [decision](../decisions/2026-07-28-transaction-soft-delete.md), [plan](../plans/2026-07-28-p225-transaction-soft-delete.md)                                          |
| P3-38 | Search paging hits Elasticsearch's `max_result_window` cliff at page 200; the REST list has no such cliff. [→ detail](#p3-38)                            | analytics, frontend    | M                                  | open            | [P1-14 review](../plans/2026-07-26-p114-transaction-list-pagination.md), [decision](../decisions/2026-07-26-transaction-list-envelope.md)                           |
| P3-39 | `account-service` cannot run `make test` or `make lint` locally (banking's half closed by P3-23 on 2026-07-28). [→ detail](#p3-39)                 | infra, DX              | S                                  | open            | [P1-15 outcome](../plans/2026-07-27-p115-categorize-auth-and-secret-rotation.md), [P3-23 plan](../plans/2026-07-28-p323-banking-uv-pyproject.md)                                                                                    |
| P3-40 | Workers share their API service's image instead of each declaring `build:`, so `compose build <svc>` cannot leave them on stale code. [→ detail](#p3-40) | infrastructure         | S                                  | done 2026-07-27 | [plan](../plans/2026-07-27-p340-worker-image-sharing.md), [findings/2026-07-25-per-worker-image-staleness.md](../findings/2026-07-25-per-worker-image-staleness.md) |
| P3-41 | 131 bare `AsyncMock()`/`MagicMock()` står ind for ports uden `spec`, så portkontrakter er uhåndhævede i testene. [→ detail](#p3-41)                      | test, cross            | M                                  | open            | [findings/2026-07-27-sync-trigger-double-value.md](../findings/2026-07-27-sync-trigger-double-value.md)                                                             |
| P3-42 | budget-service initialiserer `FastAPICache` med en Redis-backend i lifespan, men ingen rute er dekoreret med `@cache` — cachen er død infrastruktur, og redis er en dependency den ikke bruger. Afgør: dekorér de dyre read-ruter, eller fjern backend + redis-dep. | budget, deps | S | open | fundet under [P2-37](../plans/2026-07-28-p237-budget-single-install-path.md) |
| P3-43 | Implementér ADR-0005: nginx `proxy_pass` per path, frontenden på relative URLs, de 11 `CORSMiddleware` ud. [→ detail](#p3-43) | infra, frontend, cross | M | done 2026-07-28 | [plan](../plans/2026-07-28-p343-nginx-perimeter.md), [ADR-0005](../../docs/adr/0005-nginx-as-security-perimeter.md), [decision](../decisions/2026-07-28-nginx-as-perimeter.md) |
| P3-44 | `GET /api/v1/users/{id}` er `INTERNAL_API_KEY`-vogtet men ligger ikke under `/internal/`, så perimeterens præfiks-regel kan ikke lukke den. [→ detail](#p3-44) | user, infra | S | open | [ADR-0005](../../docs/adr/0005-nginx-as-security-perimeter.md), valg A i [P3-43-planen](../plans/2026-07-28-p343-nginx-perimeter.md) |
| P3-45 | nginx cacher upstream-IP'er ved config-load, så en genskabt service giver 502 gennem perimeteren indtil frontenden genstartes. [→ detail](#p3-45) | infrastructure | S | open | fundet under [P3-43 trin 3](../plans/2026-07-28-p343-nginx-perimeter.md) |
| P3-46 | `qwen3:8b` bliver OOM-dræbt når hele stakken kører, så chat-pipelinen kan ikke køres end-to-end på 7,8 GB Docker-hukommelse. [→ detail](#p3-46) | ai, infrastructure | S | open | målt under [P3-43 trin 5](../plans/2026-07-28-p343-nginx-perimeter.md) |
| P3-47 | En `location` med eget `add_header` fjerner tavst perimeterens fire security headers i den blok. [→ detail](#p3-47) | infra, frontend | S | open | [plan](../plans/2026-07-28-p325-p227-perimeter-headers-ratelimit.md#åbne-valg) |
| P3-48 | Ingen af de otte inderside-ruter har en account-guard: `AuthContext` anser en bruger for logget ind på tre af fem localStorage-nøgler, så `/dashboard` er nåelig med gyldig token og ingen valgt konto. Efter P2-40 giver det en GraphQL-fejl frem for forkerte tal — rigtigere, men stadig en dårlig skærm. `CategoriesPage.jsx:29` har allerede en ad-hoc variant at konsolidere | frontend, UX | S | open | [P2-40s Non-goals + Follow-ups](../plans/2026-07-28-p240-gateway-explicit-account-resolution.md) |
| P3-49 | `make security` kører `bandit -r app -x tests`, CI kører `bandit -ll -ii` — så gateways `make check` er **rød lokalt og grøn i CI** på et Low-fund (`B105` på `token = ""`, `auth.py:55`). En rød `make check` uden at noget er i vejen er grunden til at ingen kører den. Fix: samme flag i targettet, eller `# nosec` med item-reference | CI, cross, deps | S | open | målt under [P2-40](../plans/2026-07-28-p240-gateway-explicit-account-resolution.md#outcome) |

---

## Item details

Rows whose description outgrew a table cell. Nothing here is a summary — this is the original text, moved so the tables above stay readable. Grep an ID to land directly on its section.

### P1-13

**budget-service computes spend from at most 50 transactions.** `TransactionPort` sends no `limit`, transaction-service defaults to 50 and applies it in SQL after `ORDER BY date DESC, id DESC` — so budget-service sums the 50 newest rows and treats that as the month. Measured in dev: account 1, June 2026 → 94 tx, true spend 16 739,83, computed 5 180,32 (**69% understated**); July 2026 (budget id=9, **open**) → 41% understated. Hits three call sites: the budget widget, **`close_month`** (surplus too high → over-allocation to goals) and **F2-03 alert evaluation** (thresholds never cross). `close_month` is explicitly fail-closed against a fictional surplus from `spent=0`, but truncation produces the same thing partially and silently, so the guard never fires. Fix = point budget-service at analytics-service's canonical rules (ADR-0004), not `&limit=10000` — that also kills the `category_id is None` and `type=="expense"` divergences in the same port

**Outcome.** 8 commits: `ISpendPort` → `AnalyticsSpendPort` mod `/api/v1/analytics/overview`; `close_month` bruger `total_expenses`, linjer bruger `expenses_by_category`. Målt før/efter i kørende container: juni 5.180,32 → **16.739,83** (= Postgres eksakt), juli 10.286,17 → **17.666,17**. Fail-closed live-verificeret med analytics stoppet: summary 200/`spent=0`, close 503, `closed_at` NULL, 0 outbox. F2-03 emitterede 7 events, 5 deduped, 2 nye 100%-kryds som trunkeret forbrug aldrig kunne nå. Fire mutationer tjekket

### P1-14

**The transactions page silently shows only the 50 newest rows in the selected period.** `services/frontend/src/api/transactions.jsx:24-31` sends no `limit`; transaction-service defaults to `limit=50` and applies it after `ORDER BY date DESC, id DESC` (`rest_api.py:61`); the UI renders the array with no pagination, no total and no truncation notice. **Same mechanism as P1-13, on the surface the user actually reads.** Measured 2026-07-26 (user 1, account 1): June 2026 = 93 rows in Postgres, page shows 50 → **46% hidden**; July 61 → 11 hidden; April sits exactly on 50, one row from silently losing data. Because the cut lands after a date-descending sort, what disappears is the *oldest part of the selected period* — pick June and you see June 30 back to ~June 16. Compounds with P1-13 instead of being fixed by it: the dashboard now correctly reports June as 16 739,83 across 93 transactions while the list shows 50 of them, so the user sees a correct total that cannot be reconciled against the rows underneath — the opposite of the trust P1-13 bought. Search has the same class of ceiling hardcoded at 100 (`useTransactionSearch.jsx:59`) and ignores the active filters (`TransactionsPage.jsx:74`). Fix = thread `skip`/`limit` + a total through (needs a response-shape decision: envelope vs `X-Total-Count`), **not** `&limit=10000`. P3-06's "pagination/virtualized tx table" clause is a misclassification for the pagination half; virtualisation can stay there

**Outcome.** 12 commits. Målt mod genbygget container, grep'et før troet: juni `total_count`=93 med 50 items, juli 62, april 50 — eksakt lig Postgres; junis to sider partitionerer sættet (50+43=93, disjunkte) og BEGGE melder 93; `limit=201`/`0`/`skip=-1` → 422 hvor de før gav 500; de listede udgifter summerer til 16 709,83 = analytics' `/overview` til øren. Rækkefølgen holdt: frontendens tolerante læser landede i step 6, serverens envelope i step 11, så intet skew-vindue. Søgningen fik `filters` + `$offset` — adfærdsændring: søgning dækker nu det aktive datofilter, ikke hele historikken. **Planens Done-when-tal var arvet og forkert**: 16 739,83 kom fra P1-13's 94-rækkers-måling dagen før, mens dette items eget fund noterede 93 — én 30,00-række forsvandt imellem, så tal og sum driftede sammen. Afstemningen holder; kun literalen var stale. UI-drevet kan ikke automatiseres her (ingen Playwright/Puppeteer; `tests/e2e/` taler med API'et) og bekræftes manuelt af brugeren. Spawned undervejs: P3-36, P3-37, P2-30

### P1-15

**`/api/v1/categorize` is unauthenticated and reads `user_id` from the request body.** `categorization-service/app/adapters/inbound/categorize_api.py:29-46` — no auth dependency, no `require_internal_api_key`, app built with no global dependency (`main.py:28-35`), published on the host at `8005:8005`. `build_categorization_service(user_id=body.user_id)` layers that user's private F1-02 rules onto the engine, so the differing `tier` field is an oracle over other users' rule sets. **Demonstrated live 2026-07-26 with no credentials**: `"SHOP N PLAY"` → `tier:"fallback"` for `user_id` null and 2, but `tier:"rule", subcategory_id:5, confidence:"high"` for `user_id:1`; HTTP 200 throughout, `/docs` open on the same port. Under F1-03 those rules are auto-generated from real manual corrections, so this reconstructs a stranger's spending habits without touching a transaction endpoint, and `user_id` is a small int so enumeration is trivial. `/batch` additionally accepts an unbounded list. Fix = `require_internal_api_key` on the router (transaction-service is the only real caller — **correction 2026-07-27: it did *not* already have S2S config**; neither `transaction-service/app/config.py` nor `categorization-service/app/config.py` had `INTERNAL_API_KEY`, repo-wide grep for `INTERNAL_API_KEY|X-Internal` in categorization-service returned 0 hits, so the key had to be added on both sides rather than just a `dependencies=` parameter) + a `max_items` bound; copy user-service's `compare_digest` check (`rest_api.py:24`), not account-service's `!=` (`internal_api.py:20`). **Rotate the shared secret in the same change**: `k8s/secrets.yaml:8-10` is git-tracked in a public repo with `dev-secret-key-change-in-production` as the HS256 key shared by all 12 services — distinct from P2-15 (*how* to manage k8s secrets) and P3-02 (RS256 *later*); the value is disclosed **now**, and three services also default `INTERNAL_API_KEY` to the well-known dev string (`goal/config.py:13`, `banking/config.py:17`, `notification/config.py:11`) where user- and account-service correctly fail closed

### P1-16

**`graphql-request` kalder `new URL(url)` uden base, så den relative sti P3-43 gav den kastede
`TypeError: Invalid URL` — og hele GraphQL-læsestien var død i browseren.** Dashboard,
transaktioner og kategorier viste `Fejl: Failed to construct 'URL': Invalid URL` i stedet for
data. Introduceret 2026-07-28 af `c0418646` (P3-43 trin 2) og fundet samme dag, af P3-25's
CSP-kontrol — ikke af nogen gate. Bevist i tre uafhængige lag (browser, node uden browser,
git-arkæologi), se [finding](../findings/2026-07-28-graphql-client-rejects-relative-url.md).
**Ingen gate kunne have fanget det som repoet stod:** P3-43 verificerede GraphQL med `curl`,
hvad der er sandt om transporten men ikke kan sige noget om klienten, og de 344 frontend-tests
mocker `GraphQLClient` væk i `graphqlClient.test.jsx:12` — mocket *er* blindheden. Fixet gør
URL'en absolut i `graphqlClient.jsx` (klientens krav, ikke en konfiguration; `serviceUrls.js`
bliver relativ, så ADR-0005 er uændret) med en regressionstest i egen fil der kun stubber
netværket. **done 2026-07-28** i `68dc3db0`, verificeret i browseren og bevist rød med
regressionen genindført

### P2-01

**Extract `services/shared/messaging` (outbox worker, outbox repo, rabbitmq publisher, consumer base with DLQ+delayed**

**Outcome.** (workers = thin shims, 6 consumers on ConsumerBase). Two deliberate carve-outs: saga-command-consumers (banking, transaction) keep their own retry (saga failure-reply semantics ≠ base contract), and account's SyncOutboxRepository stays until P3-01 (sync persistence vs async-only shared repo)

### P2-02

**Extract `services/shared/auth` (real package; replace 9 copies; kill dead `jwt_utils.py`; `require_exp`)**

**Outcome.** (see package README + P3-02). **⚠️ Correction 2026-07-26**: the `require_exp` clause in this title was *built but never enabled* — `shared/auth/auth/fastapi.py:28` and `auth/jwt.py:27` default to `False` and no call site opts in (verified across all 12 `app/auth.py`). A token with no `exp` claim is accepted and never expires. Latent alone (user-service always sets `exp`), but it turns a leaked secret from 60-minute tokens into permanent ones — see P1-15. Activation tracked as **P2-26**

### P2-09

**Carry `entry_reference` + `currency` through saga import; dedupe on `(account_id, external_id)`**

**Outcome.** commits 9d80a7a6..e913e44a: migration 012 partial-unique index, three-way dedup with transition fallback, saga items carry both fields; semantics + accepted artifacts in [decisions/2026-07-16-p209-dedup-semantics.md](../decisions/2026-07-16-p209-dedup-semantics.md)

### P2-19

**Consumer hygiene sweep (with P2-01): parse inside try, retries to own queue, prefetch >1 where idempotent, no inline**

**Outcome.** (fixed goal/categorization/taxonomy fanout-republish bug). **⚠️ Correction 2026-07-26**: the "prefetch >1 where idempotent" clause did **not** ship. `shared/messaging/messaging/consumer.py:55` defaults to `DEFAULT_PREFETCH_COUNT = 1` and all five explicit `set_qos` calls pass 1 (`analytics/projection_consumer.py:77`, `analytics/embedding_consumer.py:72`, `transaction/saga_command_consumer.py:50`, `banking/saga_command_consumer.py:139`). Consequence: the ES projection handles one event at a time with a full ack round-trip between each — the throughput ceiling on the whole ADR-0003 chain during a 500-row bulk import (P3-15's chunk size). Harmless at current volume; the reason to record it is that the row read as if the ceiling had been raised

### P2-21

k8s manifest drift: 6 workloads + 1 DB live in compose but have no manifest or `kustomization.yaml` entry (notification-service/-consumer/postgres-notifications, banking-sync-scheduler, budget-month-close-scheduler, budget-alert-scheduler, analytics-embedding-consumer). `kubectl apply -k k8s/` silently yields a system with no notification feed and no automatic ADR-0003 chain. Add manifests + `DATABASE_URL_NOTIFICATION_SYNC` secret, then a CI check diffing compose services against kustomization resources so it cannot recur

### P2-22

Inbox guard on banking's saga-command consumer: `_handle_mark_sync_complete` clears the sync-claim and writes the outbox row in one transaction, but nothing dedupes the command itself. If the reply publish fails after commit (or the ACK is lost), the redelivered command re-reads a now-NULL `sync_trigger` → falls back to MANUAL → emits a **second** `BankSyncCompletedEvent` with a fresh `correlation_id`, so notification-service's `source_key` differs and the unique-constraint dedupe cannot absorb it → a spurious "ingen nye transaktioner" row, and the F1-05 quiet-sweep suppression is defeated on exactly that path. Pre-existing (it double-notified before the trigger work too), now visible. Fix = the DB-backed `processed_events` inbox the conventions already prescribe; carve-out per P2-01 means this consumer never got `ConsumerBase`'s dedup hook. Same class of gap in transaction-service's saga-command consumer — check both

**Outcome.** commit 6c77b2ef: key is `(saga_id, step_name)`, **not** the platform's `correlation_id` — saga-service puts none in command bodies, and the one on the outbox row is `saga.correlation_id`, identical for every step, so dedup on it would stall the saga at step 2. Duplicate path still *replies*: a silent ack hangs the saga to timeout. Inbox row commits with the effects, else idempotency costs retry-ability. transaction-service checked as asked — `rollback_import` already idempotent and is the only command the orchestrator itself re-emits; `bulk_import` data-safe via P2-09 but needs stored reply → P2-23

### P2-23

Stored reply for transaction-service's `bulk_import` saga command: data are already safe at redelivery (P2-09 dedup skips committed rows), but the *reply* is not — `imported_ids` comes back **empty** on the second delivery, so if the saga fails afterwards the compensation has nothing to roll back and the imported rows stay. A plain inbox guard would make it worse (it would answer with empty ids deliberately); the fix is to persist the first reply and resend it verbatim. Same mechanism would let banking's `bank_fetch_transactions` be guarded too (its reply carries the whole fetch)

### P2-25

**Transaction soft-delete decision + gone-vs-not-yet in the categorization write-back.** transaction-service hard-deletes (`postgres_transaction_repository.py:116-126`; no `deleted_at`/`is_deleted` column) against CLAUDE.md's own anti-pattern list — goal-service got soft-delete in P3-16, transactions did not. Consequence observed 2026-07-25: tx 1133 was created, categorized, then deleted mid-flight; `categorized_consumer.py:74-76` raises `_TransactionNotFoundYet`, which conflates "not committed yet" (retry correct) with "gone for good" (retry pointless) → 5 retries → DLQ. The handler already uses `PoisonMessageError` elsewhere, but with a hard delete the two states are indistinguishable, so the guard cannot be written. **Decide soft-delete first** (touches P2-09 dedup key, all read paths, ES projection, analytics aggregations — plan-first), *then* the consumer fix is trivial

**Outcome.** Landed 2026-07-28 in five commits with P3-37 (migration 013 + the predicates), which
was never a separate item — the migration alone has no value and the consumer branch alone cannot
be written. See [the decision](../decisions/2026-07-28-transaction-soft-delete.md) for the three
trade-offs (dedup excludes tombstones, saga `rollback_import` stays soft, the consumer acks rather
than DLQ'ing). **Two claims in this row were corrected by measurement.** The blast radius was
smaller than "all read paths, ES projection, analytics aggregations": ES already consumed
`transaction.deleted` into a terminal `is_deleted` flag and `_base_filters` already excluded it, so
neither was touched — the change is transaction-service plus `scripts/cleanup_pg_duplicates.py`.
And "then the consumer fix is trivial" understates which half does the work: with the branch
removed but soft-delete in place, only one of its four tests fails, because the row now *exists* and
nothing backs off. Soft-delete alone closes the DLQ path; the branch keeps a tombstone from having
its categorization overwritten. Verified on the running stack including the control (an id that
never existed must still retry and DLQ — it did, depth 2 → 3)

### P2-24

Shared internal-API client in `services/shared`: the internal owner-lookup is hand-rolled **three times** (notification-, goal- and banking-service) with three different error taxonomies — and P1-13 adds a fourth in budget-service (deliberate: a money-correctness fix should not block on this refactor). The connection pooling and auth-failure classification won in the notification hardening reach only one of them. Same consolidation `messaging.ConsumerBase` did for consumers

### P2-26

**Turn on `require_exp` in all 12 services.** The flag exists (`shared/auth/auth/fastapi.py:28`, `auth/jwt.py:27`) and defaults to `False`; no call site opts in, so a JWT without an `exp` claim verifies and never expires. **Correction 2026-07-27: not one line per `app/auth.py`.** 10 services take `require_exp=True` on the shared dependency, but gateway-service has *two* decode sites (`app/auth.py` dependency + `_decode_user_id`) and reads its key from `SECRET_KEY`, and analytics-service is not on the shared package at all — it hand-rolls PyJWT, where the option is spelled `options={"require": ["exp"]}`. jose's `require_exp=True` is **silently ignored** by PyJWT, so copying the shared spelling there enforces nothing (verified empirically). Do it together with the P1-15 secret rotation — separately it is latent, together they are the difference between a leaked key granting 60-minute access and permanent access. Correction note on P2-02 explains why this was believed done

### P2-27

**No rate limiting anywhere.** Zero hits for `slowapi\|limiter\|rate_limit\|limit_req` across `services/`, `nginx.conf` and CI. `POST /api/v1/users/login` (`user-service/.../rest_api.py:43-52`) has no throttling, lockout, backoff or CAPTCHA, and the password policy is length-only (min 8, `dto.py:10-11`) with no complexity rule and no breach check. Note the interaction with P2-11: moving bcrypt off the event loop was right, but it removed the accidental CPU brake that was the only thing slowing an attacker down — and at ~250 ms per bcrypt(12) verify, unauthenticated login is now also a cheap DoS vector. Login itself does not leak existence (same error for both branches, `service.py:109,115`); `register` does via 409 — decide that one deliberately. Where the limiter lives depends on P3-24 (there is no perimeter today), so a per-service `slowapi` on the auth routes is the pragmatic v1


**Outcome.** Landet 2026-07-28 i `474b9643`. **To** zoner à `10r/m burst=5 nodelay` på login og
register — planen foreskrev én, men målingen viste at fælles zone lod register-spam spærre alles
login. Målt: 6 igennem på frisk zone, verificeret rød uden `limit_req` (20/20), afgrænsning
bekræftet (`/users/me` og `/transactions/` urørte). **Zonen er per-IP i form og én global bucket
i praksis**, fordi `$remote_addr` er Docker-gatewayen for al host-trafik; per-IP bevist via en
sibling-container med egen bucket. **Omgåelsen er målt frem for underforstået:** 20 requests
direkte mod `:8001` gav nul 429, fordi portene stadig er på `0.0.0.0` (ADR-0005 punkt 3) — vores
egen `tests/e2e/` er beviset. Password-politik, lockout og 409-eksistensleaket er urørte.
Se [planens Outcome](../plans/2026-07-28-p325-p227-perimeter-headers-ratelimit.md#outcome)
### P2-28

**Any authenticated user can mutate or delete the global taxonomy.** `categorization-service/app/adapters/inbound/category_api.py:73-76` (`DELETE /categories/{id}`), `:132-135` (subcategories) and create/update at `:45,63,97,122` all take `_user_id: int = Depends(get_current_user_id)` — the underscore is the finding: identity is resolved and thrown away. The taxonomy is global and shared under ADR-003, so one user's delete lands in every other user's categorizations, budget lines and analytics. Needs a **decision, not just a dependency**: there is no role or admin concept anywhere in the codebase (`grep -E 'admin\|role\|is_admin'` → nothing), so either add a minimal role to the user model (couples to F2-08's user-model work) or make taxonomy mutations internal-only and expose a curated subset. ADR-003 settled ownership of the taxonomy, not authorisation over it

### P2-29

**CSV upload has no size limit, no MIME check and buffers the whole file.** `transaction-service/app/adapters/inbound/rest_api.py:141` does `content = await file.read()` with no `content_type` validation and no size guard; the parsers then reload it into `io.StringIO` (`app/application/csv_parsers/nordea.py:34`, `danske_bank.py:35`, `internal.py:34`) — three live copies at peak, not two, against the pod's `limits.memory: 512Mi`. No ASGI-level max request size and no row cap. P3-15 chunked the internal saga path only — the CSV path was not touched. Authenticated-only, so this is availability rather than breach: one user can OOM transaction-service for everyone. Pairs naturally with F2-12 (import dry-run + error report), which touches the same endpoint — kept out of P2-29 deliberately, see its Non-goals

### P2-30

**`test_budget_month_closed_e2e.py` closes the month before the spend it depends on has reached the read side.** The fixture POSTs three expenses (3 000) then immediately calls `POST /monthly-budgets/close`; since P1-13, budget-service reads spend from `analytics/overview` (`budget-service/app/adapters/outbound/analytics_port.py:40`), which is fed by the ES projection consumer. The close therefore reads `spent=0` and allocates the whole budget: all three tests fail with `5000.0 == 2000.0`. The test polls for the *allocation* but not for the *spend*. Verified 2026-07-26 that this is timing, not loss: the rows do land (9 ES hits for `"E2E expense"`, 3 000,00 per user across three runs) and `/overview` reports 3 000,00 for all three accounts afterwards. **This is why the E2E job has been red on master since before P1-14** (`e2b38207`, 2026-07-25 22:58). Latent since P1-13 moved spend to the read side — a synchronous-write assumption left behind by an async read model. Fix = poll `/overview` until `total_expenses == 3000` before closing, not a `sleep`

**Outcome.** 2 commits `a2d3eecd`, `8d306873`. Gaten poller det tal lukningen selv slår op — samme endpoint, samme `budget_period(2026, 6, 1)`-interval — med 40s loft, fordi kæden er outbox → RabbitMQ → ES-projektion og projektions-consumeren kører prefetch 1 (P2-19). **Kausalitet bevist frem for antaget**: gaten slået fra igen → 3 failed med præcis `5000.0 == 2000.0`; med gaten → 3 passed, hele suiten 24/24 lokalt. Racet er ikke marginalt — lukningen sker millisekunder efter POST'erne, så den blev tabt hver gang, også på en varm lokal stak. Fandt undervejs at **hverken analytics- (8012) eller categorization-service (8005) var i health-gaten**, selvom fixturet kalder begge; 8005 har været en udeklareret afhængighed siden testen blev skrevet, 8012 blev det da P1-13 flyttede forbruget. Begge tilføjet i `conftest.py` + `ci.yml`, som skal holdes ens

### P3-14

**Serialize bank-sync sagas per connection (deterministic correlation id)**

**Outcome.** commit f1d36d22: in-flight claim på bank_connections — ikke deterministisk correlation-id, se plan; live e2e: concurrent syncs → samme saga_id — [plan](../plans/2026-07-17-p314-serialize-bank-sync-sagas.md)

### P3-20

`scripts/cleanup_pg_duplicates.py:148` deletes straight from the write DB (`DELETE FROM transactions WHERE id = ANY(%s)`) with no outbox event, while the service's own delete path writes event+delete in one transaction. Result is a permanent one-way leak into the ES read model: tx 1119 (138,00) is `is_deleted:false` in `transactions_v2` and absent from Postgres, so analytics reports 17 666,17 for account 1 / July where the truth is 17 528,17. Nothing can self-heal it — the row that would trigger the event is gone. Matters more after P1-13, since budget-service then reads spend from that model. Fix = write the outbox row in the script's existing transaction (preferred) or call the delete API; plus a durable rule that scripts writing to a service DB are participants in its event contract

**Outcome.** 2 commits: event bygges fra kontrakt-klassen, INSERT før DELETE på samme cursor, rowcount-guard mod den omvendte fejl. Live e2e: 3 dubletter slettet → 3 outbox-rækker → alle tre `is_deleted:true` i ES, de tre bevarede urørt. Juli 17 666,17 → **17 528,17** = Postgres eksakt; juni/april fulgte med fordi to *rigtige* dubletter (864, 1024) også blev ryddet event-korrekt. Fuld id-sæt-diff: **0** fantomer for rigtige brugere, 0 manglende. Fandt undervejs at fundets "kun én række" byggede på en én-måneds-diff — de øvrige 66 er eval-fixtures → P3-21

### P3-22

**CI detection: nothing surfaces a red run**

**Outcome.** `make ci-status` → `scripts/ci_status.py`. The premise that this needed `gh auth login` was **wrong**: it conflated the `gh` CLI with the GitHub API. The repo is public, so run/job/step conclusions are readable unauthenticated — only log text is 403. Stdlib-only, no venv, no token; honours `GH_TOKEN` for the 60/hour cap and for going private later; exit 1 on red. Also reports jobs *skipped* via `needs:`, which is how e2e silently stopped running. Found banking-service red since 2026-07-17 within minutes → `ce7a23f3`. Not solved: nothing *pushes* the signal — it must be run

### P3-21

**ai-service's eval seed writes 66 fixture documents into the production ES index.** `services/ai-service/tests/eval/es_seed.py:63` seeds synthetic transactions with `is_deleted: False` straight into `transactions_v2` — the index analytics projects into and budget-service reads spend from since P1-13. Tenant-isolated in practice (users 9001/9002, no real-user impact — verified), so LOW. The cost is that it puts a permanent floor of 66 unexplained phantoms under the Postgres↔ES id-set diff, which is precisely the check that would have caught P3-20 the day it happened instead of three weeks later. Fix = seed into a dedicated `transactions_eval_v2` index (structural isolation, preferred over teardown-dependent cleanup), then add the diff as a must-be-zero assertion

### P3-19

Non-UUID `saga_id` retries to the DLQ instead of being rejected as poison: `saga_reply_consumer.py:53` checks that `saga_id` is present but not that it parses, so a malformed value reaches the `uuid` column and raises `asyncpg.DataError` — an infrastructure exception neither `except` clause catches, so `ConsumerBase` treats it as transient and burns `MAX_RETRIES`. No production path produces this (real ids are UUIDs); the value is the exception classification, which currently states "domain errors are poison, everything else transient" and is falsified by bad input. Fix = `uuid.UUID(saga_id)` inside the existing guard

### P3-24

**Decide whether the gateway is a security perimeter — write the ADR before any of P3-25/P2-27 pick a location.** Today it is not: `frontend/src/config/serviceUrls.js:2-31` has the browser talking directly to ports 8001–8010 (ten origins), and compose publishes all nine Postgres instances (5433–5441, passwords in the same file), RabbitMQ 5672 + management UI on `guest:guest`, Elasticsearch 9200 with `xpack.security.enabled: "false"`, Redis 6380 unauthenticated and Ollama 11435 — all on `0.0.0.0`, i.e. LAN-reachable. This single fact is the root cause behind three otherwise-unrelated symptoms: there is nowhere to put rate limiting or CSP, the JWT cannot move to an HttpOnly cookie (ten origins), and Swagger is open on all 12 services in every environment (none set `docs_url=None`; P3-12 covers GraphiQL on the gateway only). A demo/portfolio system may reasonably accept this — but as a written trade-off, not as an accident of compose defaults. **Datastore-halvdelen lukkede 2026-07-28 i `5ea37f0d`** — de 14 mappings binder nu `127.0.0.1`, målt 0/14 nåelige fra LAN mod 14/14 før. Denne rubrik sagde tidligere at fjernelse af host-publishing "has no downside"; **det var kun sandt for loopback-bind, ikke for at slette `ports:`** — syv host-side-forbrugere bruger portene, heraf én i CI, se [planens Steps](../plans/2026-07-28-p324-datastore-loopback-bind.md#steps). **ADR-halvdelen lukkede samme dag: [ADR-0005](../../docs/adr/0005-nginx-as-security-perimeter.md) vælger nginx — ikke gateway-service — som perimeter.** Det afgørende fund var at spørgsmålet ikke handlede om at sikre produktion: k8s har 30 ClusterIP-Services og hverken Ingress, NodePort eller LoadBalancer, og frontendens `VITE_*`-vars er ikke sat nogen steder, så de hardcodede `localhost:800X` er dem der bygges ind i imaget. Der findes altså ingen deployment hvor en perimeter ville være nåelig. Implementeringen er **P3-43**; credentials er stadig urørte og hører ikke til perimeteren

### P3-25

**No security headers.** `services/frontend/nginx.conf` is twelve lines and sets no CSP, HSTS, `X-Frame-Options`, `X-Content-Type-Options` or `Referrer-Policy`. The JWT lives in `localStorage` (`AuthContext.jsx:41-43`, read by `apiClient.jsx:8` and `chat/api/streamChat.js:23`). Mitigating and worth recording so it is not re-audited: there is **no XSS sink today** — no `dangerouslySetInnerHTML`, no `innerHTML`, no `eval()` anywhere in `src/`. This is missing defence in depth, not an exploitable path. HttpOnly cookies are blocked by P3-24. CSRF is genuinely a non-issue (header auth, not cookies) and CORS is an explicit origin list everywhere, never a wildcard. Minor extra: the JWT carries `username` and `email` claims (`user-service/app/auth.py:28-34`), so PII sits in `localStorage` in cleartext when `sub`/`user_id` would do


**Outcome.** Landet 2026-07-28 i `38634dca` + `e377a420`. Fire headers med `always` (målt på
200, 404 **og** et proxyet 422 — de to sidste er `always`-beviset). CSP'en er bevist *håndhævet*
og ikke kun leveret: kontrol med `script-src 'none'` gav violation **og** en app der ikke
mountede. **HSTS bevidst udeladt** — 0 hits på `listen 443`/`ssl_certificate` i repoet, og
browsere ignorerer headeren over HTTP, så den ville være inert og læses som dækning ved næste
audit; hører til den dag der findes en TLS-terminering. Direktiverne er målt på bundlet
(0 × `eval(`, 0 × `data:`, 0 × `url()`), og **én af planens begrundelser var forkert**: de 35
`style={{}}` kræver ikke `'unsafe-inline'`, fordi React bruger CSSOM — kun radix' scroll-lock
gør. Se [planens Outcome](../plans/2026-07-28-p325-p227-perimeter-headers-ratelimit.md#outcome).
**Itemets største udbytte var P1-16**, som kontrollen afdækkede
### P3-26

**No dependency scanning, and banking-service pins known-vulnerable versions.** `.github/workflows/` has only `ci.yml` — no dependabot, no `pip-audit`, no `npm audit`, no CodeQL. Bandit runs (`ci.yml:122-128`) but is SAST, not SCA, so it cannot see vulnerable dependencies. ~~`banking-service/requirements.txt:10` pins `python-jose[cryptography]==3.3.0`~~ **— closed 2026-07-28 by P3-23**, and the reason is worth keeping: `python-jose` was used in exactly one place in the whole service, `tests/integration/test_bank_api.py:32`. The app signs with PyJWT (`adapters/outbound/enable_banking_client.py:12`). It sat in the *runtime* list — and therefore in the image — only because there was no dev/runtime split to put it in. It is now a dev dependency at `>=3.4.0`. Likewise `fastapi==0.115.0` → resolved to 0.140.7 via `uv.lock`, so the starlette 0.38.x multipart DoS (CVE-2024-47874) is gone too. **What remains of this item is the actual scanning**: no dependabot, no `pip-audit`, no `npm audit`, no CodeQL — banking's pins are no longer the example, but nothing would have told us about them either. *CVE mapping was from memory; still confirm with `pip-audit` when the scanner lands.* Separately, `docs/security-audit-notes.md` deferred nine npm advisories to "after Phase 2" and `package-lock.json:5562-5587` still has `react-router-dom` 7.6.3 where that note's own fix range is `> 7.11.0` — Phase 2 has been code-complete since 2026-07-16, so the deferral has expired

### P3-27

**Four containers run as root; k8s has no securityContext and no NetworkPolicy.** No `USER` directive in `services/{account-service,gateway-service,frontend,serverless-health-job}/Dockerfile`; the other ten have `USER appuser`, and gateway is the most exposed of the four. The ~50 k8s Deployments have no `securityContext`/`runAsNonRoot`/`readOnlyRootFilesystem`, and there is no NetworkPolicy anywhere in a namespace where everything can reach everything. P3-01 covers non-root Docker as one clause of a large account-service refactor; the other three services are uncovered. Also: Grafana ships `admin/admin` (`k8s/monitoring/grafana.yaml:20-23`, `docker-compose.monitoring.yml:41-42`) and can read Loki, which promtail fills from every pod — not in `k8s/secrets.yaml`, not covered by P2-15

### P3-28

**Build & image hygiene — the best effort-to-payoff item in the sweep, all figures measured 2026-07-26.** (a) **gzip is off**: `frontend/nginx.conf` sets none and the base image has it commented out → 874 KB (`index-*.js` 774 751 B + css 99 056 B) uncompressed on every cold load, ~250 KB with gzip; no `Cache-Control: immutable` on hash-named assets either. (b) **No `.dockerignore` anywhere** with `context: .` on 50+ compose services: repo is 1,7 GB, of which `services/*/.venv` = 1,1 GB, `frontend/node_modules` = 228 MB, `.git` = 108 MB — and the three shared packages' **dev `.venv` are baked into every image** (`docker history`: auth 42,3 MB, messaging 32,8 MB, contracts 19,3 MB against source sizes 36K/196K/212K) = ~92 MB ballast × 12 services. (c) **uv cache kept**: every Dockerfile runs `uv sync --frozen --no-dev` without `--no-cache` (e.g. `transaction-service/Dockerfile:16`), leaving `/root/.cache` at 98 MB; images run 460–782 MB and `docker system df` reports 57 GB. (d) **The frontend Dockerfile copies the host's `node_modules` over its own install** (`frontend/Dockerfile:8-11`: `npm install` then `COPY services/frontend/ ./`) — 228 MB of wasted I/O and a latent `Cannot find module @esbuild/linux-arm64` depending on whether the developer ran `npm install` locally. One `.dockerignore` + `ENV UV_NO_CACHE=1` + two nginx lines removes ~190 MB of ~660 MB per image and fixes (d). Multi-stage is then not worth it

### P3-29

**Compose drift left over from P2-16.** (a) **No `restart:` on any datastore** — redis `:36`, postgres `:48`, rabbitmq `:65`, elasticsearch `:79`, ollama `:99` and all eight service Postgres instances (`:152,260,323,448,569,686,905,1015`). P2-16 gave restart policies to the APIs and outbox publishers but not the databases under them, so after a Docker daemon restart every app returns `unless-stopped` while its database stays down → crash-loop until someone runs `compose up` by hand. Exactly the failure class P2-16 set out to close. (b) **Elasticsearch at 771 MiB of its 1 GiB `mem_limit`** (`docker-compose.yml:86-87`) at 359 documents — the only container with a limit and the closest to an OOM kill; raise to 2g or lower `-Xmx`. (c) No resource limits on the other 55 containers (~2,5 GB measured total). (d) 26 worker containers have no healthcheck and no Dockerfile declares `HEALTHCHECK`, so a dead consumer reads as "Up". (e) Orphaned `transactions_v1` — 222 docs, 106 kb, no alias points at it; same class of drift as P3-21. P3-11 covers (c)/(d) for k8s only

### P3-30

**No frontend code splitting.** `src/App.jsx:16-23` imports all eight pages eagerly; the only `React.lazy` in the codebase is for devtools (`:72`). `vite.config.js:9-11` has just `outDir` — no `manualChunks`, no `chunkSizeWarningLimit`, no visualizer, no bundle budget in CI. Result is the single 757 KB chunk measured in P3-28, putting `recharts` (dashboard only), `graphql`+`graphql-request` (gateway hooks only) and `@microsoft/fetch-event-source` (chat only) on the login page's critical path. Smallest useful move: `React.lazy` on the five heavy routes + `manualChunks` splitting recharts and graphql

### P3-31

**Gateway opens a new connection pool per upstream call.** Six sites use `with httpx.Client(...)` inside the method: `analytics_client.py:46`, `account_client.py:26`, `budget_client.py:33`, `category_client.py:34,43`, `saga_client.py:26`. One dashboard GraphQL query (`hooks/useDashboardData/useDashboardData.jsx:17-91`) fans out to ~7 sequential upstream calls — `_overview_with_trend` (`graphql_api.py:284-297`) makes two analytics calls back-to-back — each with its own TCP handshake and no keep-alive reuse. **Explicitly not P2-04**: that is the async rewrite, deliberately rolled back and parked until measured need. Pooling is orthogonal — one module-level or lifespan-scoped `httpx.Client` per upstream, ~20 lines, no async required; per-request memoisation already exists as a house pattern (`graphql_api.py:231,242-249`). The sync-resolvers-on-an-async-router problem *is* P2-04's and stays there

### P3-32

**Routing robustness + mobile navigation.** (a) 401 does `window.location.replace('/login')` (`utils/handleUnauthorized.js:6-14`) — a hard reload with no "session expired" message and no returnUrl, so the user silently loses context; with 60-minute tokens and no refresh this fires regularly. (b) No `path="*"` inside `AppContent` (`App.jsx:31-40`) → `/foobar` renders the navbar above a blank page. (c) No account gate: Dashboard and Transactions do not handle a missing `account_id` though BudgetPage and CategoriesPage do; and `pages/AccountSelector.jsx` renders without `<Navigation>` (`App.jsx:59-62`) — no logout, no way back, reachable only by knowing the URL. (d) **Mobile navigation is effectively hidden**: `styles/Navigation.css:130-141` makes the seven links a horizontally scrolling strip with the scrollbar suppressed, so "Mål" and "Finans Chat" are unreachable in practice; no hamburger anywhere, no bottom nav, touch targets at `padding: 0.35rem 0.625rem` (`:168-171`) far under 44px, while "Logget ind som: X" and logout never collapse (`:144-151`). (d) overlaps F2-08's nav rework — do them together

### P3-33

**UI consistency: loading, errors and form validation.** (a) No skeletons anywhere; loading text uses four different verbs across eight strings ("Loader...", "Indlæser dashboard...", "Henter budget...", …) with mixed `...` and `…`; page transitions blank the whole layout (`DashboardOverview.jsx:67` returns early) causing large layout shift; no `aria-live`/`aria-busy` so none of it is announced. (b) Errors go three ways — toasts (`NotificationContext.jsx:38-39`), inline `.error-message` (`LoginPage.jsx:51`, `RegisterPage.jsx:76`, `AccountSelector.jsx:97`), and `MessageDisplay` with hardcoded inline hex bypassing the token system (`MessageDisplay.jsx:6-16`); `GoalSetup.jsx:59,101-103` shows the same error twice at once. (c) **CLAUDE.md specifies React Hook Form + Zod and neither is installed** — all seven forms are hand-rolled `useState` if-chains yielding one global error string, with no field-level errors, no `aria-invalid`, no blur validation and no focus move; `TransactionForm.jsx:61` says "Alle felter skal udfyldes." when four fields are empty and points at none, its amount input is a raw `type="number"` with no `step`/`min` despite the backend requiring ≥ 0,01 (comment at `:65-66` admits it), and `:60-63`/`:71-74` validate `category` twice. **Decide whether the convention or the code moves** — `patterns/frontend-data-patterns.md` already tracks which CLAUDE.md claims are aspirational, and this belongs on that list either way. (d) Tokens bypassed with hardcoded hex in `GoalItem.jsx:6-11,29-35` (a different palette entirely), `CategoryManagement.jsx:180`, `Navigation.css:54,84,91,97`; currency formatted three different ways; no per-route `<title>`; no refresh affordance despite `queryClient.js:36` disabling focus-refetch on the grounds that users "can refresh explicitly"

### P3-34

**Accessibility gaps.** Against a genuinely good baseline (Radix focus management, paired polite/assertive live regions, `prefers-reduced-motion`, `:focus-visible` rings, no missing alt text since there are no `<img>`): (a) `NotificationBell.jsx:82-88` — each notification is a clickable `<div>` with no `role`, `tabIndex` or `onKeyDown`, so it cannot be marked read from the keyboard, inside a `role="menu"` (`:61`) with no `menuitem` children (invalid ARIA); the dropdown closes on outside `mousedown` (`:34`) but not on Esc or Tab-out. (b) **No `role="progressbar"`/`aria-valuenow` on any progress bar** — `GoalItem.jsx:97-105`, `GoalOverview.jsx:112-115`, `BudgetProgressSection.jsx:18,40,93`, `BudgetPage.jsx:430-432`, `GoalProgressSection.jsx:23` — these are the app's primary visualisation and convey nothing to a screen reader. (c) Tabs without tab semantics (`GoalPage.jsx:51-63`). (d) No skip link to `<main>`. (e) `.visually-hidden` is defined only in `DashboardOverview.css:163` but used from `TransactionsPage.jsx:184` — works only because all CSS is one global bundle. (f) Deprecated `onKeyPress` (`AccountSelector.jsx:154`), raw emoji without `aria-hidden` (`BudgetPage.jsx:229`), wrapping labels without `htmlFor`/`id` (`CategoryManagement.jsx:157-176`)

### P3-35

**The transactions page's two read paths have different scopes, and after P1-14 they share one pager.** The REST list is **user-scoped**: `frontend/src/api/transactions.jsx:24-31` sends no `account_id`, and `useTransactions.jsx:11` puts `accountId` in the react-query key only, so the list returns every account the user owns. The search path is **account-scoped**: it goes through the gateway, which requires `X-Account-ID` (`gateway-service/.../graphql_api.py:235-239`). P1-14 unifies the page size across both modes and hangs one `Pagination` component over them, so for a multi-account user "Viser 1–50 af 93" and "93 resultater for …" would count different populations, and toggling search would silently change the scope as well as the query. Latent today only because the seed data has one account per user (verified 2026-07-26: user 1 has exactly one, and June is 93 rows both user-scoped and account-scoped). The fix is a decision before it is code — which scope is correct for the list? Account-scoping it matches the rest of the app (dashboard, budgets, goals and search are all account-scoped via `X-Account-ID`) and is probably right, but it changes what the page shows for anyone with more than one account, so it needs its own measurement

### P3-36

**Remove the transaction list's shape-tolerant reader once the envelope is deployed.** `frontend/src/api/transactions.jsx` carries an `Array.isArray(body)` branch in `unpackTransactionList` that reads the old bare-array response and substitutes `items.length` for the total. It exists **only** to buy the deploy ordering in P1-14 — the reader ships in step 6, the server envelope in step 11 — so that no bundle ever calls a differently-shaped server. It is a dated transition, not a defensive default: while it is live, a genuinely broken/rolled-back server is indistinguishable from a working one, except that the pager under-reports ("Viser 1–50 af 50" for a 93-row June). Delete the branch and its `describe('overgangsform: …')` block in `transactions.test.jsx` once transaction-service's envelope is deployed everywhere it is read (compose + k8s), i.e. not before P1-14 step 11 is out of local. Note the branch is asserted by tests, so deleting it turns a test red rather than changing behaviour silently — which is why this can be a backlog line and not a calendar reminder

### P3-37

**`transactions` has no soft-delete column, against the repo's own convention.** `information_schema` for `transaction_service.transactions` lists 18 columns and none of them is `is_deleted`/`deleted_at`, so `DELETE /api/v1/transactions/{id}` removes financial records irrecoverably — while CLAUDE.md states soft-delete + audit trail for domain entities, and sibling services follow it (`planned_transactions` in this same service soft-deletes). `scripts/cleanup_pg_duplicates.py` deletes rows outright too; P3-20 made it emit the event, but the row itself is still gone. Surfaced while verifying P1-14, where a departed June row (tx 864, 30,00) had to be traced through a *finding* rather than through the data. Needs a migration plus a `deleted_at IS NULL` predicate in `_filter_clauses` (shared by `find_filtered` and `count_filtered`, so rows and total stay consistent by construction) and a decision on whether the projection consumer deletes from ES or marks

**Outcome.** Done 2026-07-28 as part of P2-25 — see that row and
[the decision](../decisions/2026-07-28-transaction-soft-delete.md). The open question at the end
of this paragraph turned out to be already answered in code: the projection consumer *marks*
(`is_deleted: true`, scripted upsert, one-way), and had done so since before the row was written.
`scripts/cleanup_pg_duplicates.py` now soft-deletes too, and its duplicate search excludes
tombstones — without that a deleted row and its legitimate re-import form a "group" whose lowest
id is the tombstone, so the script would keep the dead row and delete the live one

### P3-38

**Search paging hits Elasticsearch's `max_result_window` cliff at page 200; the REST list has no such cliff.** `analytics-service/app/adapters/outbound/elasticsearch/query_store.py:622-631` pages with `from_=offset, size=limit`, and ES refuses `from + size > index.max_result_window` (default 10 000) with a 400 rather than an empty page — so with `PAGE_SIZE = 50` the search pager breaks at page 201, while the transactions list (Postgres `OFFSET`, verified 2026-07-26 to return `total_count` intact and `items: []` past the end) degrades quietly instead. **P1-14 is what exposes this**: before it, search was pinned at `limit: 100, offset: 0` (`useTransactionSearch.jsx:59`) and deep paging was unreachable; now the pager drives `$offset` and `pageCountOf(totalCount)` will happily render "Side 1 af 400" for a 20 000-hit search and hand the user a button that 400s. Not reachable at current volumes (largest account measured: 93 rows in a month, low thousands lifetime), which is why this is P3 and not a defect — but it is reachable by a real user with years of bank imports and a two-character query, and the failure mode is an error toast on a button the UI itself drew as valid. Note `track_total_hits=True` (`:629`) means `totalCount` stays honest past 10 000, so the pager's *arithmetic* is right and only the fetch fails — the two disagree, which is the confusing part. Options, in rough order of cost: clamp `pageCount` for the search path to `floor(max_result_window / PAGE_SIZE)` and say so in the pager; raise `max_result_window` on the index (buys headroom, does not remove the cliff, costs heap per deep page); or move search to `search_after`, which is the real fix and needs a stable tiebreaker sort plus a cursor-shaped API — i.e. a decision, since the pager is offset-shaped and `search_after` is not

### P3-23

**banking-service has no `pyproject.toml`** — the only Python service on bare `requirements.txt` besides account, so it took CI's `pip install -r` fallback branch, had no dev/runtime dependency split, and no lockfile. That is why `aiosqlite` (test-only) had to go into the runtime requirements in `ce7a23f3`, and it is the same odd-one-out that made P2-01/P2-02 adoption awkward. The sharpest consequence was not tooling inconsistency: with no `pyproject.toml` there was nowhere to put `[tool.mypy]`, so **the service whose `SyncTrigger` bug motivated P2-31 was the one service the resulting gate could not cover**.

**Outcome.** Landed 2026-07-28 in four commits. See [the plan's Outcome](../plans/2026-07-28-p323-banking-uv-pyproject.md#outcome) for the full narrative, including the two claims in this row that measurement corrected.

### P3-39

> **Halveret 2026-07-28 af P3-23.** banking-service is on uv + pyproject with a `uv.lock`, and its suite ran locally for the first time (68 passed) — the `psycopg2` source-build blocker never materialised because the service already pinned `psycopg2-binary`, so that clause of this row was wrong. What remains is **account-service only**, which is why the effort dropped to S. The paragraph below is preserved as written; read `banking-service` in it as historical.

**`account-service` and `banking-service` cannot run `make test` or `make lint` locally, and `banking-service`'s suite cannot run locally at all.** Both are `requirements.txt`-only (no `pyproject.toml`, no `uv.lock`, no `.venv`) while the other 10 Python services are on uv + pyproject. Their Makefiles invoke bare `pytest` / `ruff` (`banking-service/Makefile:9,18` — account-service is identical, same lines), so both targets die with `command not found` unless the caller happens to have those on `PATH`; `install-deps` pip-installs into whatever interpreter is active rather than a per-service venv. Repo-wide `make lint` therefore also fails — it iterates `PY_SERVICE_DIRS` and these two abort it, so the *other* eleven services' lint result is never reached. `banking-service` is worse than an inconvenience: its deps build `psycopg2` from source, which needs `pg_config` and fails on a plain macOS box, so **the only place that suite has ever run is CI** (`banking-service - Python 3.11`). Workaround used during P1-15: `uvx ruff check .` for lint, and `uv run --with-requirements requirements.txt --with pytest --with pytest-asyncio pytest tests` for account-service's tests. **Why this is worth a row rather than a shrug**: a red `make test` in these two reads as "my change broke it" when it means "the tool is absent", and — the actual risk — a green local run of everything *else* silently excludes them, so a change touching all services looks verified when two are untested. P1-15/D1 hit exactly this: the `INTERNAL_API_KEY` fail-fast needed a `conftest` change in banking-service that could only be confirmed after push. Same class as the root Makefile's `test-e2e`, which had never been locally runnable for the same reason (no root `pyproject`) until it was fixed in `6489c89a`. Options: give both services a `pyproject.toml` + `uv.lock` like the other ten (real fix, touches dependency management in two services and should be one service per commit); or keep pip but have the Makefiles shell out through `uv run --with-requirements` so the targets are self-bootstrapping (smaller, leaves the inconsistency); `psycopg2` → `psycopg2-binary` is orthogonal and needed either way for banking-service to be locally testable


### P3-40

**Workers declare their own `build:` block, so rebuilding a service leaves its workers on a stale image.** Every worker/consumer/scheduler in `docker-compose.yml` points at the *same* Dockerfile as its API service but with its own `build:`, so Compose builds and tags a separate image per compose service. `docker compose build banking-service && docker compose up -d --force-recreate banking-saga-command-consumer` therefore looks like a deploy and is not: the worker's own image was untouched, `ps` says `running`, and nothing reports a version. Filed 2026-07-27 — the finding had been open since 2026-07-25 with **no backlog item at all**, which is why it kept being rediscovered. Fix = option 1 in the finding: give workers `image: finance-tracker-<svc>` instead of `build:`, so one build produces one image that all its workers share. That also cuts build time and storage — the banking Dockerfile is currently built four times to produce four byte-identical images. Effort is S because it is a compose edit, but verify it against a worker that genuinely needs a rebuild, since the failure mode of *this* item is a verification that lies. Sibling of P3-17 (same "workers are second-class citizens of the compose file" root); do not fold them together — P3-17 is about migrations, this is about images

**Why it matters beyond local dev**: it invalidates live verification silently. During the F1-05 quiet-sweep check the API had new code while the saga-command consumer ran a 2026-07-20 image; the scenario *passed* for the wrong reason (the old consumer never set `trigger`, so the event fell back to the Pydantic default `MANUAL`, which notifies). A mixed-version system produced exactly the output the new code was supposed to produce. Detection that works today: `docker compose exec -T <worker> grep -c <new-symbol> <file>` — 0 means stale.

### P2-31

**Ingen statisk typecheck kører nogen steder.** CLAUDE.md foreskriver "mypy for type checking (zero errors policy)"; målt 2026-07-27 kalder **0 af 13 services** mypy i deres Makefile eller i CI, kun `analytics-service` har overhovedet en mypy-config (som intet invokerer), og rodens `pyrightconfig.json` er en ren IDE-hjælpefil hvis `extraPaths` dækker 2 services. Typeannotationer er derfor dokumentation, ikke begrænsninger — hvilket er hvordan `service.py` kunne sende `str` til en port der erklærer `SyncTrigger` og bryde **alle** bank-syncs i to dage uden at nogen gate blinkede. Dette er den eneste af de tre tavsheder i fundet der er generel: den anden (uspecificerede mocks, P3-41) er en konsekvens, og den tredje (forældet image) er lukket af P3-40. Rækkefølge: start med ét service og `--strict` slået fra, ellers drukner det i eksisterende fejl; banking- og account-service kan ikke være først, fordi de mangler pyproject (P3-39). Bemærk at fixet her er billigere end det ser ud: annotationerne *findes* allerede overalt, de er bare ulæste

**Outcome.** Landet 2026-07-27 over 7 trin og **8 af 12 services** (analytics som pilot, derefter user, notification, ai, budget, saga, transaction, categorization). Gaten er `uv run mypy` i hver services `Makefile` + ét CI-step gated af `TYPECHECK_SERVICES`; indrullering er ét servicenavn på en liste, rollback er at fjerne det. Niveauet er default-mypy plus `disallow_untyped_defs`, `warn_unused_ignores`, `warn_redundant_casts`, `no_implicit_optional` — identisk på alle 8. Forudsætningen var `py.typed` på alle fire `shared/*` (målt: 5 fejl uden, 16 med). Verificeret som **kontrol, ikke kun treatment** via `make verify-typecheck-gate` (8 gatede / 4 ikke-gatede, bevist i stand til at blive rød). Udbyttet var **usande kontrakter, ikke typefejl** → P2-32…P2-37. Udenfor: goal (P2-34), banking+account (P3-23), gateway (98 fejl); `tests/` er ikke dækket (→ P3-41). Fuld rapport: [planens Outcome](../plans/2026-07-27-p231-static-typecheck-gate.md#outcome) + [session-log](../sessions/2026-07-27-p231-typecheck-gate.md)

### P2-37

**Målt 2026-07-28** — og det korrigerer fundets oprindelige formulering, som påstod at
`make freeze` fandtes i hver service og bare ikke blev checket. Begge led var usande.

| Install-sti i imaget | Services |
|---|---|
| `uv sync --frozen --no-dev` | 9 — ai, analytics, categorization, gateway, goal, notification, saga, transaction, user |
| `pip install -r requirements.txt` | 3 — account, banking, budget |

For de 9 læser image og tests **samme** lockfile; drift er strukturelt umuligt og der er intet
at checke. Drift-betingelsen er at *begge* filer findes, og det gælder **præcis én** service:
**budget-service** (`fastapi==0.115.0` i requirements mod 0.136.3 i locken, `redis>=5` mod
`>=8`, og `jinja2` kun i pyproject). account og banking har ingen lockfile — de kan ikke
drifte, de har én usandt-låst kilde i stedet for to uenige (account pinner slet ikke `fastapi`,
så dens image er ikke reproducerbart).

`freeze:`-target findes i 3 af 15 services (transaction, categorization, user) — **alle tre
bygger med `uv sync --frozen` og har ingen `requirements.txt` på disk**. Levn fra før
Dockerfile-migrationen; ingen af de tre pip-services har et.

**Fix:** giv budget samme Dockerfile-form som de 9 (`uv sync --frozen --no-dev`, shared som
path-deps under `/shared/*` — mønsteret findes i `transaction-service`), slet dens
`requirements.txt`, slet de 3 døde `freeze`-targets, og læg en vagt i
`scripts/compose_check.py` mod at en service har både `uv.lock` og `requirements.txt`.
Fejlklassen forsvinder frem for at blive overvåget. account og banking får deres lockfile via
P3-23/P3-01; bankings `fastapi==0.115.0`-pin er en *særskilt* fælde (samme 204-død venter hvis
den kommer på typecheck-gaten), ikke en drift.

> *Efterskrift 2026-07-28:* banking landede via P3-23 (**11 af 12** installerer nu fra `uv.lock`,
> kun account mangler). Fælden var reel men **ikke armeret**: ingen rute i banking annoterede
> `-> None`, så der var ingen 204-assertion at udløse. Den er nu væk med pinnet (fastapi 0.140.7).

### P2-39

**Browser-automatisering som ejet instrument.** Repoet har **nul** browser-lag: ingen
playwright/puppeteer/cypress/selenium i `package.json`, `uv.lock` eller nogen
`requirements.txt` — de eneste hits er dev-notes-prosa der konstaterer fraværet. Argumentet er
**ikke "flere tests"**: de to eksisterende suiter var *begge* grønne gennem hele P1-16, hvor hver
bruger så `Fejl: Failed to construct 'URL': Invalid URL` i stedet for data. De 346 jsdom-tests
mocker `GraphQLClient` væk (`graphqlClient.test.jsx:12`), og `tests/e2e/` går bevidst uden om
perimeteren (`nginx.conf:51`). Det er et **andet instrument**, ikke mere af det samme.

**P3-25 beviste både værdien og grænsen.** Fundet kom kun fra at *drive* appen — men proben var
headless Chrome med `--dump-dom`, `sleep`, `kill -9`, en throwaway-nginx og webroot kopieret til
scratchpad. **Intet af det er checket ind**, og forudsætningen for at gentage det ligger i stedet
som uoprydet tilstand i dev-stakken (bruger `csp_probe` id 368, konto 371). Den ramte sin grænse i
samme session: `'unsafe-inline'` kan først bevises nødvendig *i appen* når en radix-dialog åbnes,
og "proben klikker ikke".

Valgt løsning og de tre afviste alternativer (ad hoc-script ind, `pytest-playwright` i Python-e2e,
selvstændigt CI-job) står i [decision-noten](../decisions/2026-07-28-browser-automation-instrument.md).
Kort: `@playwright/test` i `services/frontend/`, kørt i det **eksisterende** `e2e-tests`-job
(`ci.yml:279-344`) — det eneste sted i CI hvor stakken inkl. nginx på 3000 kører, så vi undgår en
anden fuld `compose up --build`.

**Scope er to tests, ikke en portering af de 346:** (1) dashboardet viser rigtige tal gennem den
rigtige klient — P1-16-klassen; (2) CSP håndhæves i appen efter et dialog-klik — P3-25's C2.
Begge **verificeres røde ved mutation** før de tælles; en browser-test der aldrig er set fejle er
værre end ingen, fordi den ligner dækning. Fixturen skal eje session-seedingen: selvsigneret
HS256 (som `tests/e2e/_env.py`) plus **fem** localStorage-nøgler (`authStorage.js:1`) — glemmes
`account_id` svarer `periodOverview` med **tavse nuller i stedet for en fejl**, altså en
grøn-udseende test på en tom app. Peg på `127.0.0.1:3000`, ikke `localhost` (P3-43's første måling
ramte en Vite dev-server på `[::1]:3000`). Ryd samtidig `Makefile:49,91` op, som siger 5173 hvor
porten reelt er 3000.

**Shippet 2026-07-28. Tre ting blev anderledes end planlagt, og alle tre er målinger:**

1. **Suiten er tre tests, ikke to.** Fixturen fik sin egen vagt, fordi den har fire kontrakter mod
   produktkode der kan drifte tavst. Vagten viste sig selv at være grøn under `script-src 'none'`
   — på en app uden en linje kørende JS — og måtte hærdes. Grøn-på-ingenting ramte altså inde i
   selve instrumentet, i første forsøg.
2. **Planens mutations-kontrol holdt ikke.** P1-16 genindført gør *begge* suiter røde: bug'en fik
   sin egen jsdom-regressionstest da den blev rettet, så linjen er dobbeltdækket i dag. Kontrollen
   der beviser at instrumentet er nyt er i stedet `totalIncome → totalIncomeTYPO` i
   `DASHBOARD_QUERY`: **`npm test` 346 passed, browser-suiten 2 failed.** GraphQL-dokumentet
   valideres mod det rigtige schema af intet andet i repoet.
3. **"Tavse nuller uden `account_id`" var den forkerte diagnose** — og kontrollen afdækkede det
   ved at blive **grøn**: gateway'en falder tilbage til `accounts[0]`, og P3-25's testbruger havde
   to konti (→ P2-40). Trin 8's oprydning stødte samtidig på at der ikke findes en sletningssti
   for konti og brugere (→ P2-41), så kun de fem transaktioner blev ryddet.

**C2 er afgjort med et tal:** `style-src` uden `'unsafe-inline'` → **1 violation**
(`style-src-elem`/inline) ved dialog-åbningen, **0** på `/dashboard`. Direktivet er nødvendigt, og
præcis kun af den grund `nginx.conf` angiver.

### P2-40

**Gateway'ens `accounts[0]`-fallback: vælg eksplicit eller fejl ærligt.** Manglede
`X-Account-ID` på en GraphQL-læsning, returnerede `get_account_id_from_headers` ikke en fejl men
`int(accounts[0]...)` — den første række account-service tilfældigvis svarede med.
`postgresql_account_repository.get_all` har ingen `ORDER BY`, så "første konto" er uspecificeret.
For en enkeltkonto-bruger usynligt; for en flerkonto-bruger et **plausibelt tal fra den forkerte
konto, præsenteret som den valgte**. Værre end en tom skærm, fordi en tom skærm bliver rapporteret.

Fixet er eksplicit `name = 'Default Account'` — en regel repoet allerede havde
(`account_creation_consumer` + det partielle unique index `one_default_per_user` fra migration
`002`) — eller `None`, hvorefter `_require_account_id` giver den fejl der allerede fandtes. Der
skulle altså ikke bygges en fejlsti, kun holdes op med at forhindre den.

**Itemet bar også et instrument-hul:** browser-suiten seedede én konto pr. bruger, og med én konto
er enhver fallback det rigtige svar — derfor blev P2-39's `X-Account-ID`-mutation grøn i *alle*
suiter. `twoAccountSession` + `dashboard-scopes-to-selected-account.spec.js` lukker det, og samme
mutation er nu rød i præcis den spec.

Se [Outcome](../plans/2026-07-28-p240-gateway-explicit-account-resolution.md#outcome) for de målte
tal, for hvorfor den *naive* tokonto-opstilling ikke viser fejlen (defaultkontoen oprettes først og
er derfor `accounts[0]`), og for det negative resultat om rækkefølge-stabilitet. Afledte items:
**P3-48** (frontend-vagt), **P3-49** (`make security` vs. CI's bandit).

### P2-38

**Et CI-job kan hænge i seks timer uden at nogen får det at vide — to manglende grænser i serie.**
Målt 2026-07-28 på run `30381676420`: analytics' `Run tests` collectede 123 tests og udsendte
derefter **ikke én testlinje i 836 sekunder**, hvor den foregående grønne kørsel havde første
`PASSED` **36 s** efter collection. De 36 s er `es_container`-fixturen (pull + boot af ES); i den
hængte kørsel kom containeren aldrig op. **Bevist transient, ikke forårsaget af ændringen:** en
genkørsel af samme commit uden kodeændring blev grøn, og pushet rørte nul analytics- eller
shared-filer. Fejlen er ikke flaken — det er at intet oversætter den til et signal.
**To af de oprindelige påstande her var forkerte, målt under P2-38 og rettet 2026-07-29:**
(1) `grep -c timeout-minutes .github/workflows/ci.yml` gav **1**, ikke 0 — P2-39 havde sat den på
`e2e-tests`, så det var 4 af 5 job-definitioner der manglede, ikke 5.
(2) `es_container`-fixturen manglede **ikke** en wait-timeout: `testcontainers` 4.14.2 sætter selv
`_startup_timeout = TC_MAX_TRIES × TC_POOLING_INTERVAL` = **120 s** og rejser en meget læsbar
`TimeoutError` med endpoint og hint. Og de **836 s beviser** at hængen ikke lå der — en hængende
wait var fejlet efter 120 s. Den lå i `docker_client.run(...)`'s image-**pull**, som kaldes *før*
wait-strategien og er ubundet uden nogen knap i 4.14.2. Den ydre grænse er derfor den eneste der
kunne fange denne klasse, altså `timeout-minutes` — ikke "begge grænser i serie". Klassen er
fortsat den samme som
[banking's CI-job der aldrig kunne collecte](../findings/2026-07-25-banking-ci-could-not-collect.md):
**en gate der ikke kan rapportere fejl.** Skærpende omstændigheder, alle observeret: logs
udleveres først når jobbet slutter (`BlobNotFound` mens det kørte), så diagnosen krævede at man
*først gav op og dernæst undersøgte*; baselinen på 36 s fandtes kun fordi tidligere kørsler
tilfældigvis lå i loggen, for **der er ingen alarm på varighed**; og de øvrige 18 jobs var grønne,
så kørslen rapporterede `in_progress` i det uendelige. **Leveret 2026-07-29:** `timeout-minutes`
på alle 5 job-definitioner efter målt baseline (`repo-lint` 5, `python-services` 8,
`shared-packages` 5, `frontend` 5, `e2e-tests` 30 fra P2-39), plus fixturens grænse skrevet
eksplicit som en *pin* mod at pakke-defaulten eller `TC_MAX_TRIES`/`TC_POOLING_INTERVAL` flytter
sig. Grænsen er verificeret rød: `repo-lint` med `timeout-minutes: 1` + `sleep 120` blev afbrudt
efter 72 s (run 30405860162). **Aflæsnings-forbehold der koster tid hvis man ikke kender det:**
GitHub rapporterer en timeout som `cancelled`, ikke `failure`, og loggen skriver kun
`The operation was canceled.` — ordet *timeout* optræder aldrig og grænsen navngives ikke, så
`gh run view --log-failed` returnerer **tomt med rc=1**. Signalet er "job `cancelled` + varighed ≈
grænsen", og det er derfor den målte baseline står i en kommentar ved hver grænse. Cache af
`docker.elastic.co`-imaget er stadig en *overvejelse*, ikke en udpeget årsag: registryet svarede på
0,47 s fra udviklermaskinen under hændelsen — men bemærk at pull-stien nu er udpeget som der hvor
de 836 s lå, hvilket gør cachen mere relevant end da fundet blev skrevet

### P3-41

**131 bare `AsyncMock()`/`MagicMock()` mod 9 spec'd, fordelt på 10 services** (transaction 24, banking 21 → nu 20, categorization 19, goal 15, analytics 14, ai 12, user 12, account 5, budget 5 med 7 spec'd, saga 4). Hvor mocken står ind for en **port**, betyder det at portens erklærede kontrakt ikke håndhæves nogen steder i testene: `banking-service`s ni `try_claim_sync`-tests sendte alle en `str` mod en `SyncTrigger`-port og var alle grønne. Vær præcis om hvad `spec=` køber: den fanger forkerte *metodenavne*, ikke forkerte *argumenttyper* — den ville ikke selv have fanget fejlen i fundet. Den er stadig værd at have (den fanger den tilstødende fejl, hvor et refactor omdøber en portmetode og mocken glad svarer på det gamle navn), men **P2-31 lukkede kun typehullet i `app/`** — og det ændrer regnestykket her. *Korrigeret 2026-07-27, da P2-31 landede:* alle 8 gatede services kører `packages = ["app"]`, så de 131 testfiler er nu det største usikrede areal i den kode gaten ellers dækker. Den oprindelige rækkefølge-begrundelse ("P2-31 først, ellers lukkes det forkerte hul") er dermed opfyldt og udtømt: `spec=` er ikke længere det svagere alternativ til en typecheck, den er den eneste kontrol der findes inde i `tests/`. Præcisionen holder stadig — den fanger navne, ikke argumenttyper — så alternativet "tag `tests/` med i mypy-scope" bør vejes mod dette item frem for at antages underlegent. Ikke alle 131 er ports — mocks der står ind for `httpx`-klienter eller clocks er uskyldige, så dette er en gennemgang, ikke en søg-og-erstat

### P3-44

**`GET /api/v1/users/{user_id}` er `INTERNAL_API_KEY`-vogtet
(`user-service/app/adapters/inbound/rest_api.py:67`, guard `:74`) men ligger ikke under et
`/internal/`-segment.** Perimeteren (ADR-0005) er en positiv allowlist af præfikser, og
`location /api/v1/users` er nødt til at være der — `/register`, `/login` og `/me` bor under
samme præfiks. Ruten er altså publiceret på den offentlige overflade.

**Det er ikke en bypass.** Guarden afviser stadig requests uden nøglen, så konsekvensen er en
S2S-overflade der er *synlig* udefra, ikke åben. Derfor S og ikke en sikkerhedshastesag.

**Hvorfor det ikke blev lukket i P3-43 (valg A):** alternativet var
`location = /api/v1/users/me` før en regex-`deny` på `^/api/v1/users/[^/]+$`. Det virker, men
køber lukningen med en **ordningsafhængighed i nginx.conf som ingen test fanger når den
brydes** — og rule 5 kan ikke udtrykke et præfiks-forbud mod noget der ikke er et præfiks
(assertion 3 regner i præfikser; en `location` med modifier rapporteres netop *fordi* reglen
ikke kan bedømme den). En tavs regression i en sikkerhedsregel er dyrere end en dokumenteret,
vogtet rute.

**Fixet:** flyt ruten til `/api/v1/internal/users/{id}`, så den falder ind under det præfiks
rule 5 allerede forbyder, og deny-backstoppen dækker den uden en ny regel. Kaldere skal
opdateres samtidig — find dem med `grep -rn "USER_SERVICE_URL" services/` før flytningen, og
husk at `INTERNAL_PREFIXES` i `scripts/compose_check.py` derefter dækker den automatisk.
Advarslen i `services/frontend/nginx.conf` over `location /api/v1/users` fjernes som sidste
skridt — den er kvitteringen for at itemet er lukket.

### P3-46

**`qwen3:8b` (5,2 GB) bliver OOM-dræbt når hele compose-stakken kører.** Målt 2026-07-28 under
P3-43 trin 5: to på hinanden følgende chat-requests endte begge i `event: error` /
`{"code":"internal_error"}`, med `ollama._types.ResponseError: an error was encountered while
running the model: unexpected EOF (status code: 500)` i ai-service og
`llama_server.go:1035 msg="llama-server process no longer running" ... string="signal: killed"`
i ollama. Docker Desktop har **7,8 GB** i alt; `qwen3:8b` 5,2 GB plus `bge-m3` 1,2 GB plus de
~2,5 GB de 55 containere måler i forvejen går ikke op.

**Kontrolleret at det ikke er perimeteren:** samme request direkte mod `127.0.0.1:8007`, uden
nginx, fejler identisk. Fejlen ligger under HTTP-laget, i model-runneren.

**Hvad det koster:** chat-featuren kan ikke verificeres end-to-end på denne maskine mens
stakken kører, og det er derfor P3-43's "done when" ikke kunne opgøres for chat-SSE'ens
*pipeline* — kun for dens transport (se planens Outcome). Enhver fremtidig verifikation af
ai-service rammer samme mur.

**Retninger, i stigende omkostning:** (a) hæv Docker Desktops memory-allokering — gratis hvis
maskinen har RAM, og bør prøves først; (b) brug `qwen3:4b` (2,5 GB) også til prose i
development og reservér `8b` til en profil, hvilket koster prosakvalitet og gør at det verificerede
ikke er det konfigurerede; (c) `mem_limit` + `OLLAMA_MAX_LOADED_MODELS=1` så OOM'en bliver en
ærlig afvisning frem for et dræbt subprocess. Bemærk at (c) ikke løser noget, den gør
fejlmoden læsbar — hvilket stadig er værd at have, jf. at symptomet i dag er en generisk
dansk fejlbesked i UI'et.

### P3-45

**nginx slår upstream-navne op én gang, ved config-load — ikke per request.** Målt
2026-07-28 under P3-43 trin 3: efter `docker compose up -d` havde genskabt de elleve
services gav *hele* flowet gennem `:3000` **502**, med `connect() failed (111: Connection
refused) ... upstream: "http://172.18.0.17:8001/..."` i nginx' error-log. user-services nye
container lå på `.16`. `docker compose restart frontend` løste det.

Det er bagsiden af den rettelse trin 1 allerede skrev ind i planens Risks-tabel: fordi
opslaget sker ved load, er `depends_on` et krav og ikke en bekvemmelighed — men *samme*
egenskab betyder at nginx bagefter holder en IP der kan blive forældet uden at noget
signalerer det. Vigtigt: fejlmoden er ærlig (502, ikke tavs forkert routing), og den rammer
alle ruter på én gang, så den er svær at overse. Det er derfor dette er S og ikke blocker.

**Omkostningen i dag** er en fælde i arbejdsgangen, ikke i produktet: enhver
`docker compose up -d --build <service>` efterlader perimeteren død for netop den service
indtil frontenden genstartes, og symptomet (502 på alt) ligner "backenden er nede" frem for
"nginx har en gammel adresse". Præcis den forveksling kostede tid da den blev fundet.

**Formen på fixet:** `resolver 127.0.0.11 valid=10s;` (Dockers embedded DNS) plus at føre
upstream gennem en variabel, da nginx kun re-resolver når `proxy_pass` indeholder en
variabel:

```
set $upstream_user user-service:8001;
proxy_pass http://$upstream_user;
```

**Vejes eksplicit, fordi det ikke er gratis:** en variabel i `proxy_pass` slår
config-load-valideringen fra, og dermed mister vi netop den egenskab trin 1 målte —
`nginx -t` fejler i dag med `host not found in upstream` og **exit 1**, så en tastefejl i et
servicenavn opdages før start. Med variabler bliver samme tastefejl en 502 ved første
request. Det er ikke en ren forbedring, det er et bytte: statisk validering for dynamisk
genopslag. Rule 5's assertion 1 dækker en del af tabet (den verificerer navn *og*
container-port mod compose), og det er argumentet for at byttet er acceptabelt — men
afgørelsen hører i itemet, ikke i en commit hvis emne er noget andet. Alternativet er at
lade den stå og skrive arbejdsgangen ned (`restart frontend` efter recreate), hvilket er
gratis men afhænger af at man husker det.

### P3-43

**Implementér [ADR-0005](../../docs/adr/0005-nginx-as-security-perimeter.md): nginx som perimeter.** `proxy_pass` per path fra frontendens nginx til de ti services, `serviceUrls.js` på relative URLs, og de 11 `CORSMiddleware` + `CORS_ORIGINS`-envs ud, fordi kaldene bliver same-origin. Ruter-tabellen er allerede verificeret entydig i ADR'en — alle ti adskiller sig på andet path-segment efter `/api/v1`, så der er ingen kollision at løse. Fire ting ADR'en har målt frem, som ellers først dukker op undervejs: (1) **SSE brækker på default-config** — `ai-service`s `/api/v1/chat/stream` returnerer `EventSourceResponse`, og nginx buffrer som default, så den location kræver `proxy_buffering off` plus hævet `proxy_read_timeout`; (2) **positiv allowlist, ikke catch-all** — `/api/v1/internal/*` (account) og `/api/v1/categorize` (categorization) er `INTERNAL_API_KEY`-vogtede, og en `location /api/ { proxy_pass … }` ville publicere dem; (3) **perimeteren lukker ikke service-portene** — 8001–8012 bliver på `0.0.0.0`, og at lukke dem kræver først at `tests/e2e/conftest.py`s otte direkte health-polls (8001–8006, 8010, 8012 — ikke identisk med browserens ti origins) får en vej ind; (4) **intet bevogter nginx.conf mod drift** — `scripts/compose_check.py` kender den ikke, så en ny service kan tilføjes uden proxy-regel og fejle først i browseren; en femte regel dér er den naturlige plads. Oplåser P3-25 og P2-27

### P3-47

**En `location` med sit eget `add_header` fjerner tavst alle fire security headers i den blok.**
nginx' `add_header` nedarves kun til en `location` der ikke selv sætter én. `nginx.conf` har i
dag bevidst ingen andre `add_header`, så P3-25's fire headers gælder alle 20 locations — men
**P3-28 vil tilføje `Cache-Control: immutable` på assets**, og i samme øjeblik står den location
uden CSP, `nosniff`, `X-Frame-Options` og `Referrer-Policy`, uden at noget fejler. Det er samme
fejlmode rule 5 findes for: en konfiguration der ser rigtig ud og ikke er det. Fixet er en regel
i `scripts/compose_check.py` der kræver at enhver `location` med `add_header` gentager de fire
— ~15 linjer, og filen har allerede parseren fra rule 5. **Holdt ude af P3-25 med vilje:**
STATUS.md skylder allerede en omdøbning af "build hygiene" (rule 5 er en sikkerhedsregel, ikke
en build-regel), og P2-21 vil også have en ny regel til compose-vs-kustomization-diffen. At
afgøre regel-nummerering og filnavn som bivirkning af et S-item er hvordan man ender med et
navn der ikke passer. Risikoen står i `nginx.conf` med reference hertil, så den ikke kun findes
i en plan
