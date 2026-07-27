# dev-notes index

One line per document. Add yours when you add a file (see `dev-notes` skill), and keep the
hook to **one clause** — it exists to help you decide whether to open the file, so the
document itself is where detail belongs. `make notes-check` fails on a file that is missing
here. Session logs are indexed separately in [sessions/00-SESSIONS.md](sessions/00-SESSIONS.md).

## Meta
- [STATUS.md](STATUS.md) — where the work stands: active plan, next up, open findings, standing traps. **Read first.**
- [README.md](README.md) — how this knowledge base works: structure, conventions, statuses.

## Architecture (living documents)
- [architecture/overview.md](architecture/overview.md) — system map, core patterns, data flows, the 5 systemic problems. **Start here.**
- [architecture/infrastructure.md](architecture/infrastructure.md) — compose/k8s/CI/monitoring topology + measured cross-service duplication map.
- [architecture/services/user-service.md](architecture/services/user-service.md) — auth service + how services/shared is consumed; outbox reference implementation.
- [architecture/services/transaction-service.md](architecture/services/transaction-service.md) — tx CRUD, CSV/bulk import, saga participant, taxonomy read-copies, 4 workers.
- [architecture/services/account-budget-goal-services.md](architecture/services/account-budget-goal-services.md) — the three CRUD siblings + their duplication; money flows (month-close → surplus → goal).
- [architecture/services/banking-and-saga-services.md](architecture/services/banking-and-saga-services.md) — PSD2/Enable Banking + saga orchestration, bank_sync flow end-to-end.
- [architecture/services/categorization-and-ai-services.md](architecture/services/categorization-and-ai-services.md) — rule-tier pipeline, taxonomy ownership (ADR-003), SSE chat pipeline, ChromaDB.
- [architecture/services/gateway-service.md](architecture/services/gateway-service.md) — read BFF (REST + GraphQL), fan-out reality, stubs, monolith footprint.
- [architecture/services/frontend.md](architecture/services/frontend.md) — React SPA: TanStack Query (no Redux), 3 API clients, direct service coupling.
- [architecture/services/notification-service.md](architecture/services/notification-service.md) — F1-01 in-app feed: terminal consumer of 3 triggers, source_key idempotency, REST feed + bell UI.

## Patterns (living documents)
- [patterns/README.md](patterns/README.md) — pattern index: table of all patterns with canonical implementations. **Start here for "how do we do X".**
- [patterns/hexagonal-architecture.md](patterns/hexagonal-architecture.md) — layering, ports/adapters, canonical layout; honest enforcement status (archon only in ai+analytics).
- [patterns/transactional-outbox.md](patterns/transactional-outbox.md) — atomic write+event, SKIP LOCKED worker mechanics; user-service is the reference.
- [patterns/idempotent-consumers.md](patterns/idempotent-consumers.md) — inbox dedup, self-healing full-state events, DLQ+retry, consumer anti-patterns.
- [patterns/saga-orchestration.md](patterns/saga-orchestration.md) — orchestrator + command/reply conventions, compensation, honest-failure rule.
- [patterns/cqrs-es-read-store.md](patterns/cqrs-es-read-store.md) — ES read-side (ADR-0004), sole-writer rule, hybrid search, trade-offs.
- [patterns/read-copies-and-denormalization.md](patterns/read-copies-and-denormalization.md) — taxonomy read-copies (ADR-003), denormalized names, cache-not-truth rules.
- [patterns/categorization-pipeline.md](patterns/categorization-pipeline.md) — tier ladder, rule priority ladder 10/50/100, correction feedback loop.
- [patterns/csv-parser-registry.md](patterns/csv-parser-registry.md) — BankCSVParser Protocol + registry, danish-format rules, golden files, adding a bank.
- [patterns/import-dedup.md](patterns/import-dedup.md) — external_id vs fuzzy dedup, three-way rule, accepted gaps (P2-09 digest).
- [patterns/frontend-data-patterns.md](patterns/frontend-data-patterns.md) — TanStack Query + crudFactory house patterns; which CLAUDE.md bits are aspirational.

## Findings
- [findings/2026-07-07-architecture-audit.md](findings/2026-07-07-architecture-audit.md) — full codebase audit: 10 CRITICAL, 27 HIGH, ~45 MEDIUM, ~40 LOW, with file:line evidence.
- [findings/2026-07-12-goal-migration-004-sqlite.md](findings/2026-07-12-goal-migration-004-sqlite.md) — goal migration 004 Postgres-only + fixture migrated wrong DB; resolved 2026-07-17 (F1-04 wave 0).
- [findings/2026-07-17-goal-delete-fk-500.md](findings/2026-07-17-goal-delete-fk-500.md) — goal hard-delete with allocation history → FK 500 (LOW); resolved 2026-07-17 by P3-16 soft-delete.
- [findings/2026-07-20-goal-reached-not-emitted-on-allocation.md](findings/2026-07-20-goal-reached-not-emitted-on-allocation.md) — surplus-allocation completing a goal emits no event → no goal-reached notification on the auto path (MEDIUM, → F1-08)
- [findings/2026-07-25-k8s-manifest-drift.md](findings/2026-07-25-k8s-manifest-drift.md) — 6 workloads + 1 DB in compose have no k8s manifest (F1-01/F1-05/F1-07/F2-03/AI-20) (MEDIUM, → P2-21).
- [findings/2026-07-25-banking-ci-could-not-collect.md](findings/2026-07-25-banking-ci-could-not-collect.md) — banking-service's CI-job kunne aldrig collecte sine tests (`DATABASE_URL` mangler + ingen conftest), maskeret af et tidligere `ruff format`-fejl i samme job (MEDIUM, resolved 2026-07-25).
- [findings/2026-07-25-worker-migration-ordering.md](findings/2026-07-25-worker-migration-ordering.md) — migrations are a side effect of the API container's `CMD`; workers override `command:` and skip them, so k8s workers crash-loop until the API catches up (LOW, systemic, → P3-17)
- [findings/2026-07-25-budget-spend-truncated-at-50.md](findings/2026-07-25-budget-spend-truncated-at-50.md) — budget-service sends no `limit`, so spend is summed from the 50 newest transactions (HIGH, → P1-13).
- [findings/2026-07-25-transaction-hard-delete-categorized-dlq.md](findings/2026-07-25-transaction-hard-delete-categorized-dlq.md) — transactions are hard-deleted, so the categorization write-back cannot tell "not yet" from "gone" and retries a deleted row to the DLQ (MEDIUM, → P2-25)
- [findings/2026-07-25-cleanup-script-desyncs-read-model.md](findings/2026-07-25-cleanup-script-desyncs-read-model.md) — `cleanup_pg_duplicates.py` sletter uden om outboxen, så ES beholder fantom-rækker for evigt (MEDIUM, resolved 2026-07-26 af P3-20; "kun én række" korrigeret — fundet diffede kun én måned).
- [findings/2026-07-26-eval-seed-writes-to-prod-index.md](findings/2026-07-26-eval-seed-writes-to-prod-index.md) — ai-services eval-harness seeder 66 fixtures direkte i produktions-indexet `transactions_v2` (LOW, → P3-21).
- [findings/2026-07-25-per-worker-image-staleness.md](findings/2026-07-25-per-worker-image-staleness.md) — every worker carried its own `build:` block, so `compose build <svc>` left its workers on a stale image (MEDIUM, resolved 2026-07-27 af P3-40).
- [findings/2026-07-25-saga-reply-non-uuid-poison.md](findings/2026-07-25-saga-reply-non-uuid-poison.md) — a malformed `saga_id` raises `asyncpg.DataError` past both `except` clauses, so it retries instead of being rejected as poison (LOW, → P3-19)
- [findings/2026-07-26-product-surface-sweep.md](findings/2026-07-26-product-surface-sweep.md) — four-part sweep of what the backlog was not looking at: **the user domain was never written** (no password change, no reset, no deletion, no GDPR), the gateway is not a perimeter, UX/a11y gaps, and 190 MB/image of build ballast (HIGH, → P2-26..29, P3-24..34, F2-08..13).
- [findings/2026-07-26-transaction-list-truncated-at-50.md](findings/2026-07-26-transaction-list-truncated-at-50.md) — the transactions page shows 50 of June's 93 rows with no pagination or total (HIGH, → P1-14).
- [findings/2026-07-26-categorize-endpoint-unauthenticated.md](findings/2026-07-26-categorize-endpoint-unauthenticated.md) — `/api/v1/categorize` has no auth and takes `user_id` from the body, so the `tier` field is an oracle over other users' private F1-02 rules (CRITICAL, → P1-15).
- [findings/2026-07-27-gateway-default-account-307.md](findings/2026-07-27-gateway-default-account-307.md) — gatewayen kaldte account-service uden trailing slash, fik 307, og `httpx` følger ikke redirects (MEDIUM, løst i P1-15).
- [findings/2026-07-27-e2e-alert-categorization-race.md](findings/2026-07-27-e2e-alert-categorization-race.md) — budget-alert-suiten ventede på transaction-DB'en mens scheduleren læser analytics' ES-read-side, og gættede på "stabil kategori" mod en pipeline der altid omskriver (MEDIUM, løst i P1-15).
- [findings/2026-07-27-outbox-port-declares-foreign-entity.md](findings/2026-07-27-outbox-port-declares-foreign-entity.md) — outbox-porten lover domænets `OutboxEntry`, adapteren leverer shared's klasse af samme navn; 7 services, latent fordi felterne er identiske (LOW, → P2-32).
- [findings/2026-07-27-internal-api-key-optional-but-mandatory.md](findings/2026-07-27-internal-api-key-optional-but-mandatory.md) — `INTERNAL_API_KEY` er typet `str | None` i 6 services, men obligatorisk i mindst 3; ikke ét forkert mønster seks steder, men to legitime mønstre hvor det obligatoriske bruger det valgfries type (LOW, → P2-33).
- [findings/2026-07-27-sync-trigger-double-value.md](findings/2026-07-27-sync-trigger-double-value.md) — dobbelt `.value` brød **alle** bank-syncs i to dage; tre lag tavshed (bar AsyncMock, ingen typecheck nogen steder, forældet image) (HIGH, fix i `34e68040`, rodårsag → P2-31/P3-41).

## Backlog & plans
- [backlog/BACKLOG.md](backlog/BACKLOG.md) — technical backlog (P1 security/money → P2 systemic → P3 consistency), linked to finding IDs. P1 done 2026-07-07.
- [backlog/FEATURES.md](backlog/FEATURES.md) — feature backlog (F1 finish-half-built → F2 high-value → F3 bets), each with existing-scaffolding leverage + prerequisites.
- [backlog/AI-IMPROVEMENTS.md](backlog/AI-IMPROVEMENTS.md) — AI-service ideas: RAG ladder (hybrid search, reranking, multi-hop), router/responder upgrades, eval-first sequencing.
- [backlog/ML-CATEGORIZATION.md](backlog/ML-CATEGORIZATION.md) — ML categorization: getting-started ladder (merchant memory → baseline → shadow mode), feedback flywheel, hierarchical/zero-shot subcategory smarts.
- [plans/2026-07-07-refactoring-roadmap.md](plans/2026-07-07-refactoring-roadmap.md) — 4-phase execution strategy for the technical backlog, with verification approach.
- [plans/2026-07-07-feature-roadmap.md](plans/2026-07-07-feature-roadmap.md) — feature sequencing interleaved with refactor phases + build sketches for the top items.
- [plans/2026-07-11-es-analytics-integration.md](plans/2026-07-11-es-analytics-integration.md) — rebase phase-1-fixes onto master's ES analytics read-side (ADR-0004), bring-up/backfill/dual-read re-verify, + AI-19..21 ES-for-chat proposals.
- [plans/2026-07-12-ai-service-es-chat.md](plans/2026-07-12-ai-service-es-chat.md) — ai-service onto the ES read-store: AI-01 eval gate → AI-19 structured intents → AI-20 hybrid search replaces ChromaDB → AI-21 slots, + cleanup + chat-UI steps.
- [plans/2026-07-17-user-rules-and-feedback-loop.md](plans/2026-07-17-user-rules-and-feedback-loop.md) — F1-02+F1-03: rules CRUD/UI + correction feedback loop (learned corrections stored as auto-managed user rules, priority ladder 10/50/100).
- [plans/2026-07-17-f104-goal-allocation-completion.md](plans/2026-07-17-f104-goal-allocation-completion.md) — F1-04: make the shipped allocation backend reachable — default-goal API, history/unallocated read APIs, close-month button + goals UI.
- [plans/2026-07-17-p316-goal-soft-delete.md](plans/2026-07-17-p316-goal-soft-delete.md) — P3-16: goal soft-delete (deleted_at) fixes FK 500 on delete-with-history.
- [plans/2026-07-17-f107-scheduled-month-close.md](plans/2026-07-17-f107-scheduled-month-close.md) — F1-07: day-7 auto-close worker (domain due-rule, repo sweep-query, scheduler container); new trigger only, close semantics untouched.
- [plans/2026-07-17-p314-serialize-bank-sync-sagas.md](plans/2026-07-17-p314-serialize-bank-sync-sagas.md) — P3-14: in-flight sync-claim på bank_connections (atomic claim/steal/TTL, status-check ved konflikt); F1-05-prerequisite.
- [plans/2026-07-17-f105-scheduled-bank-sync.md](plans/2026-07-17-f105-scheduled-bank-sync.md) — F1-05: nightly sync-scheduler (staleness-regel >24h, worker-loop pattern, samme start_sync_saga use case); fuldender ADR-0003-kæden sync→close→goal.
- [plans/2026-07-20-f101-notification-service-mvp.md](plans/2026-07-20-f101-notification-service-mvp.md) — F1-01: notification-service fra stub → hexagonal consumer.
- [plans/2026-07-25-notification-service-hardening.md](plans/2026-07-25-notification-service-hardening.md) — post-F1-01/F2-03 review fixes: red CI (`ruff format`), `trigger` on `BankSyncCompletedEvent` so nightly quiet syncs stop notifying (rides the P3-14 claim, no saga change), + adapter/test/docstring polish.
- [plans/2026-07-26-p320-cleanup-script-outbox.md](plans/2026-07-26-p320-cleanup-script-outbox.md) — P3-20: cleanup-scriptet skriver `TransactionDeletedEvent` i samme transaktion som sin DELETE (event bygget fra kontrakt-klassen, rowcount-guard mod den omvendte fejl).
- [plans/2026-07-25-p222-saga-inbox-and-loose-ends.md](plans/2026-07-25-p222-saga-inbox-and-loose-ends.md) — P2-22: inbox guard på `mark_sync_complete` med nøgle `(saga_id, step_name)` (platformens `correlation_id`-nøgle duer ikke for saga-kommandoer).
- [plans/2026-07-25-p113-budget-spend-from-analytics.md](plans/2026-07-25-p113-budget-spend-from-analytics.md) — P1-13: budget-service læser forbrug fra analytics' `/overview` (ADR-0004's kanoniske regler) i stedet for 50 trunkerede rækker.
- [plans/2026-07-26-p114-transaction-list-pagination.md](plans/2026-07-26-p114-transaction-list-pagination.md) — P1-14: `{total_count, items}` på transaktionslisten + prev/next-pager med "Viser 1–50 af 93".
- [plans/2026-07-27-p115-categorize-auth-and-secret-rotation.md](plans/2026-07-27-p115-categorize-auth-and-secret-rotation.md) — P1-15+P2-26: `require_internal_api_key` på `/categorize` (afsender før håndhæver) + `user_id` fjernet fra DTO'en fordi ingen legitim kalder sender det + rotation af den delte HS256-nøgle til `${VAR:?}`-interpolation (39 literals) + `require_exp` på 11 shared-kaldsteder og analytics' hånd-rullede.
- [plans/2026-07-27-p340-worker-image-sharing.md](plans/2026-07-27-p340-worker-image-sharing.md) — P3-40: de 26 workers deler deres API-services image i stedet for at bygge deres eget; A/B-verificeret mod den kommando der er brudt i dag.
- [plans/2026-07-27-p231-static-typecheck-gate.md](plans/2026-07-27-p231-static-typecheck-gate.md) — P2-31: mypy som hård gate, pilot analytics-service; målt at default-mypy fanger `SyncTrigger`-fejlen, men kun når shared-pakkerne har `py.typed`.
- [plans/2026-07-20-f203-mid-month-budget-alerts.md](plans/2026-07-20-f203-mid-month-budget-alerts.md) — F2-03: budget-alert-scheduler (worker-loop) evaluerer åbne budgetter for løbende måned → `budget.line_threshold_crossed` (80%/100%) → notification-service.

## Decisions
- [decisions/2026-07-13-embed-worker-placement.md](decisions/2026-07-13-embed-worker-placement.md) — AI-20 embedding writer: separate consumer in analytics-service on own queue `analytics.embeddings`, partial-update of `description_vector`.
- [decisions/2026-07-16-p209-dedup-semantics.md](decisions/2026-07-16-p209-dedup-semantics.md) — P2-09: three-way dedup rule (external_id + in-batch set + NULL-scoped fuzzy fallback), IntegrityError-as-honest-saga-failure, event_version stays 1, accepted transition artifacts.
- [decisions/2026-07-17-learned-corrections-as-rules.md](decisions/2026-07-17-learned-corrections-as-rules.md) — F1-03: corrections stored as auto-managed user rules (priority ladder 10/50/100), not merchant rows; `is_user_confirmed` superseded.
- [decisions/2026-07-17-manual-month-close-button.md](decisions/2026-07-17-manual-month-close-button.md) — F1-04: manual "Luk måned"-knap supersedes ADR-0003 out-of-scope; scheduled day-7 close → F1-07.
- [decisions/2026-07-25-budget-spend-from-analytics.md](decisions/2026-07-25-budget-spend-from-analytics.md) — P1-13: budget-service læser forbrug fra analytics' `/overview` (ADR-0004's kanoniske regler).
- [decisions/2026-07-26-ci-feedback-loop.md](decisions/2026-07-26-ci-feedback-loop.md) — to-lags ruff-gate: pre-commit hook (staged filer) + repo-bredt `repo-lint`-job. Hverken hook eller CI alene er nok; tests holdes bevidst ude af hooken.
- [decisions/2026-07-26-transaction-list-envelope.md](decisions/2026-07-26-transaction-list-envelope.md) — P1-14: transaktionslisten returnerer `{total_count, items}` (husets konvention fra analytics/gateway) frem for `X-Total-Count`, som har nul præcedens og kræver `expose_headers` for en direkte browser-klient.
- [decisions/2026-07-27-categorize-internal-only.md](decisions/2026-07-27-categorize-internal-only.md) — P1-15: `/categorize` er S2S-only med router-level guard, og `user_id` blev **fjernet** fra DTO'en frem for hegnet ind.
- [decisions/2026-07-17-scheduler-pattern-worker-loop.md](decisions/2026-07-17-scheduler-pattern-worker-loop.md) — periodic jobs = in-service worker-loop containers (outbox-worker shape), not KEDA cron; idempotency mandatory, single replica, injected clock.

## Sessions
- [sessions/00-SESSIONS.md](sessions/00-SESSIONS.md) — session-log index, newest first. Written after significant work; not part of the load-context path.

## Templates
- [templates/plan.md](templates/plan.md) · [templates/decision.md](templates/decision.md) · [templates/finding.md](templates/finding.md) · [templates/session.md](templates/session.md)
