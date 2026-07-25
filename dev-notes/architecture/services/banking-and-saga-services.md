---
title: banking-service + saga-service
updated: 2026-07-07
source: architecture audit 2026-07-07
---

# banking-service (8009) & saga-service (8011)

## banking-service — PSD2 via Enable Banking

Hexagonal-ish: `adapters/inbound/bank_api.py` → `BankingService` → ports → Postgres repos, `AccountServiceAdapter` (HTTP), `EnableBankingClient`. Processes: API, outbox publisher, saga command consumer, account projection consumer, **sync-scheduler** (*F1-05, 2026-07-17*: `app/workers/sync_scheduler.py`, worker-loop pattern — nightly auto-sync når `last_synced_at` er >`SYNC_EVERY_HOURS` (24) gammel, tjekket hvert tick; samme `start_sync_saga` use case som knappen, P3-14-claimet forhindrer races; udløbet consent skippes med reconsent-WARNING = v1-reconsent-fladen).

- Endpoints under `/api/v1/bank`: `available-banks`, `connect` (JWT + ownership check), `callback` (no JWT; single-use `state` consumed via atomic `UPDATE…RETURNING`, TTL 15 min), `connections` list, `connections/{id}/sync` (202 → `saga_id`), `DELETE connections/{id}`.
- `EnableBankingClient`: **sync** `httpx.Client`; RS256 JWT signed per request with app PEM; paginated `/transactions` via `continuation_key`; startup PEM signing smoke test.
- Storage: `bank_connections` (stores EB `session_id` **in plaintext** — it is the durable data-access credential; consent `valid_until` never persisted → `expires_at` always NULL, `is_expired` dead code), `pending_authorizations`, `accounts_projection`, outbox + inbox tables.

## saga-service — generic orchestration engine

`SagaOrchestrator` + `SagaRegistry` with pluggable `SagaDefinition`; one concrete saga: `BankSyncSagaDefinition`. Four processes: status API (`GET /api/v1/sagas/{id}` — **no auth**), start consumer (`saga.*.start`), reply consumer (`saga.reply.#`), outbox publisher, timeout worker (poll 30s, 300s timeout on `updated_at`).

- State machine: saga `started → completed | compensating → failed | timed_out`; steps logged in `saga_step_log`; context stored as JSON TEXT in `saga_instances` (unique `correlation_id`).
- Commands emitted via saga-service's own outbox (transactional); participants publish replies directly (not outboxed).
- Compensation: backwards walk over succeeded steps; only `import_transactions` has a compensator (`rollback_import`); compensation reply outcome is **ignored** (no success param).
- Timeout: flips status to `timed_out` and does nothing else — no compensation, and it also kills `compensating` sagas.

## bank_sync saga flow

connect → callback (session created, connections stored) → sync request (outbox `saga.bank_sync.start`; *P3-14, 2026-07-17*: atomic in-flight claim på `bank_connections.sync_saga_id/sync_started_at` i samme transaktion som start-eventet — concurrent requests får samme saga_id retur med `already_running: true`; ved konflikt tjekkes claimets saga-status via saga-service (kaldens JWT videresendt), terminal → claim steales, ukendt → fail-active med `SYNC_CLAIM_TTL_SECONDS`=600 backstop; `mark_sync_complete` frigiver claimet saga_id-scoped) → start consumer creates instance → `saga.cmd.bank_fetch_transactions` → banking fetches from EB (sync client in async consumer!) and replies with **all transaction items inline** → items stored into saga context (re-serialized on every update; multi-MB rows/messages) → `saga.cmd.bulk_import_transactions` → transaction-service bulk import → `saga.cmd.mark_sync_complete` → banking sets `last_synced_at` → completed. Frontend polls saga status.

~~Identity loss: `entry_reference`/`transaction_id` and `currency` from EB are **dropped** before import~~ — **fixed by P2-09 (2026-07-16)**: saga items carry `external_id` + `currency`, and dedup is `(account_id, external_id)` with the fuzzy `(date, amount, description)` key only as a NULL-scoped fallback. See [decisions/2026-07-16-p209-dedup-semantics.md](../../decisions/2026-07-16-p209-dedup-semantics.md).

**Command-level idempotency (P2-22, 2026-07-25).** `mark_sync_complete` guards on an inbox
row keyed `f"{saga_id}:{step_name}"` in banking's existing `processed_events`, written in
the *same* transaction as the claim release and the outbox row. Without it a redelivered
command read the already-cleared `sync_trigger` as NULL → MANUAL → emitted a **second**
`BankSyncCompletedEvent` with a fresh `correlation_id`, so notification-service computed a
different `source_key` and its unique constraint could not absorb it: one ghost "ingen nye
transaktioner" per redelivery, and F1-05's quiet-sweep suppression defeated on that path.
The duplicate path still *replies* — a silent ack would hang the saga to timeout. The key is
step-scoped, not saga-scoped, because the platform's `correlation_id` key is identical for
all steps of a saga; see [patterns/idempotent-consumers.md](../../patterns/idempotent-consumers.md)
§1a. `bank_fetch_transactions` is deliberately left unguarded (its reply carries the whole
fetch, so a skip-and-ack would import 0).

## Open problems

See [findings/2026-07-07-architecture-audit.md](../../findings/2026-07-07-architecture-audit.md). Headliners: **IDOR on disconnect and connection-listing (CRITICAL)**, **unauthenticated saga status API leaks fetched bank transactions (CRITICAL)**, timeout abandons sagas without compensation (HIGH), sync EB client blocks event loop / starves aio_pika heartbeats (HIGH), no locking/versioning on saga rows (HIGH), consent expiry never checked (HIGH), saga context as transaction payload bus (HIGH), sqlite in-memory default DATABASE_URL in saga config (MEDIUM), immediate/unbounded-tempo retries duplicated 5× (MEDIUM).

## Strengths

Outbox on both sides with SKIP LOCKED; atomic single-use OAuth state; orchestrator advances state + enqueues next command in one transaction; callback error→redirect mapping with correlation refs.
