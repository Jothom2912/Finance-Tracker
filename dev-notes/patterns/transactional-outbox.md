---
title: "Pattern: transactional outbox"
updated: 2026-07-17
source: architecture audit 2026-07-07; user-service doc
---

# Transactional outbox

**Problem**: publishing an event after a DB commit (or vice versa) is a dual-write — one
side can fail and the system silently diverges.

**Solution**: the domain write and an `outbox_events` row are inserted in the **same
transaction** (via the service's Unit of Work). A separate worker process polls the table
and publishes to RabbitMQ. Delivery is **at-least-once** — consumers must be idempotent
(see [idempotent-consumers](idempotent-consumers.md)).

## Reference implementation — user-service

See [architecture/services/user-service.md](../architecture/services/user-service.md) for detail.

1. **Write path**: `POST /register` → UoW: insert user + insert `UserCreatedEvent` outbox
   row → single commit. No dual-write.
2. **Worker** (`services/user-service/app/workers/outbox_publisher.py`, own container):
   polls every 2s with
   `SELECT … WHERE status IN ('pending','failed') AND next_attempt_at <= now ORDER BY created_at LIMIT 20 FOR UPDATE SKIP LOCKED`
   → publish persistent messages to topic exchange `finans_tracker.events` (routing key =
   `event_type`) → mark published/failed with backoff `min(2^attempts*5, 300)s` → one
   commit per batch.
3. **Table shape**: `outbox_events(status, attempts, next_attempt_at, …)` + poll index
   `ix_outbox_pending_poll` matching the predicate.

Key properties: `FOR UPDATE SKIP LOCKED` makes the worker horizontally scalable; the poll
index matches the WHERE clause; exponential backoff prevents hot-looping on a broken event.

## Where it's used

Every event-producing service (8 copies): user, transaction, budget, goal, account,
banking, categorization, saga. Saga-service outboxes its **commands** too — the
orchestrator advances state and enqueues the next command in one transaction
([saga-orchestration](saga-orchestration.md)).

## Scripts are participants in the contract, not observers of it

**A script that writes to a service's database owes that service's events.** The outbox
guarantee is a property of the *table*, not of the application code that usually touches
it — a `DELETE` issued by a maintenance script diverges the read model exactly as surely
as one issued by a buggy use case.

This is not hypothetical: `scripts/cleanup_pg_duplicates.py` deleted duplicate transactions
straight from `transactions` for months. Every deleted row stayed alive in `transactions_v2`
([findings/2026-07-25-cleanup-script-desyncs-read-model.md](../findings/2026-07-25-cleanup-script-desyncs-read-model.md)),
and the damage is **permanent** — the row that would trigger the delete event is already
gone, so no retry, replay or self-healing consumer can ever notice. Read models self-heal
against *missed* events; they have no defence against events that were never emitted.
Only a full reindex recovers.

Rules for anything under `scripts/` that writes to a service DB:

1. **Write the outbox row in the same transaction as the domain write.** Same connection,
   same commit. Mirror the service's own use case.
2. **Build the event from the real contract class**, never as hand-assembled JSON — then a
   new required field breaks the script loudly instead of emitting a payload consumers
   silently cannot parse.
3. **Run it in the owning service's venv** (`uv run --project services/<svc>`) — that is
   what makes `contracts` importable, and it is the right dependency direction anyway.
4. **Assert the row counts match before committing.** Outboxing more deletes than you
   deleted tombstones live rows — the inverse failure, and equally unrecoverable since
   `is_deleted` is terminal in ES.

Reading from a service DB and publishing to MQ is *not* a violation:
`scripts/backfill_category_names.py` re-emits `TransactionCategorizedEvent` from
categorization-service's own data and writes nothing. The rule is about writes behind the
outbox, not about scripts touching RabbitMQ.

## Gotchas / open ends

- **Copy-paste ×8, already drifting** — systemic problem #1 in
  [architecture/overview.md](../architecture/overview.md); `shared/contracts` proves the
  uv path-dependency mechanism for consolidation. See
  [backlog/BACKLOG.md](../backlog/BACKLOG.md) (P2 shared-lib items).
- **No purge / dead-letter cap** on outbox tables — they grow forever (audit MEDIUM).
- Saga **replies** are NOT outboxed — participants publish them directly
  ([banking-and-saga-services](../architecture/services/banking-and-saga-services.md)).
- account-service's worker is a ~70% semantic re-implementation, and the sync/async driver
  split means two different `DATABASE_URL` schemes per process — deployment footgun
  ([account-budget-goal-services](../architecture/services/account-budget-goal-services.md)).
