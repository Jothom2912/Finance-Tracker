# Backlog

Prioritized work queue. IDs are stable — never renumber. Effort: S (<½ day), M (1–2 days), L (multi-day).
Finding IDs (C/H/M/L…) refer to [findings/2026-07-07-architecture-audit.md](../findings/2026-07-07-architecture-audit.md).
Execution strategy: [plans/2026-07-07-refactoring-roadmap.md](../plans/2026-07-07-refactoring-roadmap.md).

## P1 — Critical (security holes, money-corruption, data loss)

**Phase 1 COMPLETE (2026-07-07)** — all items implemented with regression tests, verified green per service; since committed to master (e.g. saga auth/rollback in 3d64643b). See [sessions/2026-07-07-phase1-p1-fixes.md](../sessions/2026-07-07-phase1-p1-fixes.md). Two deploy actions required (see session log): delete+recreate the `account_service.account_creation` RabbitMQ queue (new DLQ args), and users must re-ingest AI vectors once (versioned collection).

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

> Partial-scope carry-overs from Phase 1 (added to P2/P3 tracking):
> - P1-08 left `.env` files still tracked (`services/{budget,categorization,saga}-service/example.env` are examples and fine; the real tracked `.env` risk is covered by `**/.env` gitignore — none currently tracked). Git history rewrite for the purged PII backup is **still pending a user decision** (only needed if the repo is ever shared).
> - P1-02: budget `create` still relies on the `(account_id, month, year)` unique constraint (not user-scoped) — a cross-user create for the same account/period would 500. Accounts are single-owner so it's latent; noted under M21/P3-03 area.
> - P1-05: account-groups are authenticated but not ownership-scoped (no owner column) — remains a known limitation; candidate new backlog item if group data becomes sensitive.

## P2 — Important (systemic debt, perf, at-least-once hygiene)

**Phase 2 code-COMPLETE (updated 2026-07-16)** — wave-B adoption done 2026-07-15, P2-09 shipped 2026-07-16 ([sessions/2026-07-16-p209-external-id-currency.md](../sessions/2026-07-16-p209-external-id-currency.md)). Only P2-15 (k8s secrets, pure infra) remains. (Historical surveys: [sessions/2026-07-15-phase2-wave-b-resume.md](../sessions/2026-07-15-phase2-wave-b-resume.md), [sessions/2026-07-07-phase2-in-flight.md](../sessions/2026-07-07-phase2-in-flight.md).)

| ID | Title | Area | Effort | Status | Links |
|----|-------|------|--------|--------|-------|
| P2-01 | Extract `services/shared/messaging` (outbox worker, outbox repo, rabbitmq publisher, consumer base with DLQ+delayed retry) — migrate all 8 services | cross | L | **done 2026-07-15** — all 8 outbox services on the shared package (workers = thin shims, 6 consumers on ConsumerBase). Two deliberate carve-outs: saga-command-consumers (banking, transaction) keep their own retry (saga failure-reply semantics ≠ base contract), and account's SyncOutboxRepository stays until P3-01 (sync persistence vs async-only shared repo) | H18, M1–M5 |
| P2-02 | Extract `services/shared/auth` (real package; replace 9 copies; kill dead `jwt_utils.py`; `require_exp`) | cross | M | **done 2026-07-15** — all 10 services on the shared package; dead jwt_utils deleted earlier; token *minting* stays local in user/budget/account by design (see package README + P3-02) | H18, M4 (gateway L6) |
| P2-03 | Move `budget_period.py` to shared (3 byte-identical copies) | cross | S | **done 2026-07-15** — gateway, budget, account, analytics all import from finans-tracker-domain; analytics keeps only its two analytics-specific extensions locally | H18 |
| P2-04 | Gateway async rewrite: shared AsyncClient per upstream, `asyncio.gather` for independent calls, per-request memoization of tx/taxonomy fetches, retry+breaker helper | gateway | M | partially done, rest deliberately rolled back (2026-07-12): memoization shipped; the async conversion was reverted to sync because master's ADR-0004 analytics stack is sync and the legacy read path is slated for post-cutover deletion — redo async (if still needed) after that cleanup. Legacy-stien slettet 2026-07-13 (session-log): full-history-fetch + memoization-fundene bortfaldt; async kun ved målt behov | H13, H1/H2-gw, M11 |
| P2-05 | Import dedup: batch anti-join query + composite index + in-batch set + unique partial index backstop | transaction | M | done (committed e778990b: batch anti-join, in-batch seen-set, migration 011) | H15 |
| P2-06 | Wire rules DB into rule engine; consumer uses `CategorizationService` + shared provider (TTL) | categorization | M | done (2026-07-12: `main()`/`_categorize` were left half-migrated → NameError crash-loop; finished the provider wiring, verified live + 51 unit tests) | H19, H20 |
| P2-07 | Async EB client (`httpx.AsyncClient`); page caps; Decimal amounts | banking | M | done (committed 31ae3b6a) | H16, L, M19 |
| P2-08 | Persist consent `valid_until`; gate sync on expiry → 409 "reconsent needed" | banking | S | done (committed 31ae3b6a) | H9 |
| P2-09 | Carry `entry_reference` + `currency` through saga import; dedupe on `(account_id, external_id)` | banking, transaction | M | **done 2026-07-16** (commits 9d80a7a6..e913e44a: migration 012 partial-unique index, three-way dedup with transition fallback, saga items carry both fields; semantics + accepted artifacts in [decisions/2026-07-16-p209-dedup-semantics.md](../decisions/2026-07-16-p209-dedup-semantics.md)) | H10 |
| P2-10 | Saga robustness: `FOR UPDATE` on saga rows; timeout → compensation (not abandonment); don't timeout `compensating` (scoped: H17 staging deferred) | saga | L | done (committed 3d64643b, with new lock/status-API tests) | H7, H8 |
| P2-11 | Sync bcrypt → thread offload; catch IntegrityError → 409 on register | user | S | done (2026-07-15: unit 32p + integration 16p green; conftest bug fixed in fee7a5ea) | H1, L |
| P2-12 | Fix broken response caches (delete them); Redis URL from settings, close on shutdown | transaction, budget | S | done (committed c8a20088) | M9, M10 |
| P2-13 | Fix goal event `user_id` (pass resolved owner) | goal | S | done (agent reported green) | H5 |
| P2-14 | CI: add categorization/banking/saga to matrix; un-neuter bandit; fail e2e job when tests skipped; align root Makefile | infra | S | done (committed 02d1dba6: matrix +4 services, bandit -ll -ii hard-fail, e2e health-gate + CI abort-on-unreachable, root Makefile PY_SERVICE_DIRS) | H12, H27 |
| P2-15 | k8s secrets via secretGenerator/SOPS; remove real EB app id from tracked files | infra | M | open (deferred) | H11 |
| P2-16 | Compose hardening: healthchecks + restart policies on APIs, restart for account-outbox-publisher, `depends_on: service_healthy`; fix ai-service Ollama drift (models + base URL) | infra | S | done (committed 0a4b50e2, live-verified full stack green) | M29, H21 |
| P2-17 | Frontend: delete dead Budget module + dead files; JWT `exp` check at bootstrap; fix login 403 fallback | frontend | S | done (committed 4ffb32b9) | H22–H24 |
| P2-18 | Frontend: single `useGoals()` hook; centralized invalidation helper for all financial query keys; drop refreshTrigger + sleep-based forceRefresh | frontend | M | done (committed 4ffb32b9 + 23f6c6bd) | H25, M26 |
| P2-19 | Consumer hygiene sweep (with P2-01): parse inside try, retries to own queue, prefetch >1 where idempotent, no inline sleeps | cross | M | done 2026-07-15 via P2-01 adoption: parse-inside-try everywhere, retries to own queue (fixed goal/categorization/taxonomy fanout-republish bug) | M1–M3 |
| P2-20 | Outbox lifecycle: per-entry commit, max-attempts dead state, purge published rows + prune `processed_events` | cross | M | done 2026-07-15 via P2-01 adoption: shared worker defaults to per-entry commit; max-attempts dead-state + purge available (opt-in per service, not yet enabled anywhere) | M4, M32 |

## P3 — Nice-to-have (consistency, hygiene, docs)

| ID | Title | Area | Effort | Status | Links |
|----|-------|------|--------|--------|-------|
| P3-01 | account-service async migration + monolith-residue purge (dead auth/config/db code, pinned deps, non-root Docker, migrations out of API process) | account | L | open | M23, L |
| P3-02 | RS256 JWT plan + real S2S credentials (kill budget's forged user tokens) — write ADR first | cross | L | open | H2, M16 |
| P3-03 | Deprecate legacy `/api/v1/budgets` domain | budget | M | open | M21 |
| P3-04 | Event-driven ChromaDB sync (consume transaction events; handle deletes); wire or delete decorative ai ports | ai | L | **done 2026-07-14** — ports-halvdelen 2026-07-12; sync-halvdelen løst af AI-20-cutover (event-synced ES-index erstatter ChromaDB; Chroma-koden slettes efter bake, plan 2026-07-12 trin 12) | M24 |
| P3-05 | Batch user lookup for account groups (kill N+1 HTTP in repo) | account, user | M | open | H26 |
| P3-06 | Frontend: shared formatters everywhere; camelCase normalization at API boundary; pagination/virtualized tx table; accountId into AuthContext | frontend | M | open | M27, M28 |
| P3-07 | Repo hygiene: delete root node_modules/package-lock, dumps/, monolith debris, test_chromadb_sanity*, metrics-patch.json relocation, frontend build/ untracking, redundant goal-service-ci.yml | repo | S | open — ai-service-delen done 2026-07-12 (test_chromadb_sanity*/ + .pytest_cache slettet fra disk; var allerede gitignorede/utrackede; brudt sanity-script git rm'et) | L |
| P3-08 | Unify ADR numbering (migrate `docs/ADR-00N-*` into `docs/adr/` sequence) | docs | S | open | L |
| P3-09 | `event_id` on BaseEvent; projection dedup on it; freeze `event_type` per contract | contracts | M | open | M7, L |
| P3-10 | Timezone-aware timestamps everywhere (shared util in P2-01 package) | cross | M | open | M18 |
| P3-11 | Observability: `/metrics` on services or at least saga-service in Prometheus targets; worker liveness probes; resource requests baseline | infra | L | open | M30, M31 |
| P3-12 | Gateway: rename `AnalyticsService`→`DashboardReadService`; GraphiQL gated to dev; depth limits; 401 semantics; REST exception mapping | gateway | M | open | M15, M25, L |
| P3-13 | E2E coverage: bank-sync saga, categorization outcomes, ai-service smoke; health-gate all 10 services | tests | M | open | H12 |
| P3-14 | Serialize bank-sync sagas per connection (deterministic correlation id) | banking | S | open | M8 |
| P3-15 | Bulk-import item-count limits vs saga: `BulkCreateTransactionDTO.items` is 1..500 — an EB fetch with 0 or >500 items raises ValidationError in `_handle_bulk_import` → 3 retries → saga failure. Chunk in the consumer (or relax bounds for the internal path) | transaction | S | open (found during P2-09) | — |
