---
title: "Pattern: saga orchestration"
updated: 2026-07-17
source: architecture audit 2026-07-07; P2-09 decision 2026-07-16
---

# Saga orchestration

Long-running cross-service workflows use an **orchestrated saga**: saga-service runs a
state machine and talks to participants via command/reply events over the topic exchange.
Chosen over choreography so compensation and status live in one place (frontend polls
`GET /api/v1/sagas/{id}`).

Full detail: [architecture/services/banking-and-saga-services.md](../architecture/services/banking-and-saga-services.md).

## Shape

- **Engine**: `SagaOrchestrator` + `SagaRegistry` with pluggable `SagaDefinition`; one
  concrete saga today: `BankSyncSagaDefinition`.
- **State machine**: `started → completed | compensating → failed | timed_out`; steps in
  `saga_step_log`; context as JSON in `saga_instances` (unique `correlation_id`).
- **Commands are outboxed** — the orchestrator advances state and enqueues the next
  command in one transaction ([transactional-outbox](transactional-outbox.md)). Replies
  from participants are published directly (not outboxed).
- **Compensation**: backwards walk over succeeded steps; `bulk_import` compensates with
  `rollback_import` (hard delete in transaction-service — ⚠ exception to the soft-delete
  rule, and failures are swallowed).
- **Participants**: transaction-service (`saga_command_consumer`:
  `saga.cmd.bulk_import_transactions` / `rollback_import` → `saga.reply.*`) and
  banking-service (fetch + `mark_sync_complete`).

## Conventions

- Routing keys: `saga.<name>.start`, `saga.cmd.<step>`, `saga.reply.#`.
- **A failed step must reply failure honestly** — P2-09 chose IntegrityError-as-saga-failure
  over `ON CONFLICT DO NOTHING` precisely so `imported_ids` accounting stays correct for
  compensation ([decisions/2026-07-16-p209-dedup-semantics](../decisions/2026-07-16-p209-dedup-semantics.md)).
- Saga item dicts stay **untyped** in contracts (they round-trip through JSON context);
  consumers read with `.get()` + defaults so deploy order doesn't matter (same decision).

## Gotchas / open ends

- **Timeout worker abandons without compensation** and also kills `compensating` sagas
  (HIGH, open).
- **Saga context as payload bus**: bank fetch replies with *all transactions inline* →
  multi-MB context rows re-serialized on every update (HIGH, open).
- ~~Double-click on sync ⇒ two concurrent sagas~~ **fixed by P3-14 (2026-07-17)**:
  in-flight claim on `bank_connections` (atomic claim + start-event in one transaction;
  conflict → status-check via saga-service with the caller's JWT, terminal claims are
  stolen, unknown status fails active with a 600 s TTL backstop). Concurrent requests
  get the same `saga_id` back (`already_running: true`).
- Status API is unauthenticated (CRITICAL finding; check status before building on it).
