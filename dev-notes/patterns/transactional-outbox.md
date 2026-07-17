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
