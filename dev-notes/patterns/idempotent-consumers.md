---
title: "Pattern: idempotent consumers (inbox, full-state events, DLQ + retry)"
updated: 2026-07-17
source: architecture audit 2026-07-07; embed-worker decision 2026-07-13
---

# Idempotent consumers

The outbox gives **at-least-once** delivery, so every consumer must tolerate duplicates
and redelivery. Three sub-patterns combine to make that safe.

## 1. Inbox dedup (`processed_events`)

DB-backed, never in-memory. Two variants in the repo:

- **Inbox table**: `processed_events` with unique `(message_id, consumer_name)` —
  transaction-service is the canonical example; the categorization result path writes
  result + outbox event + inbox row **in one transaction**
  ([categorization-and-ai-services](../architecture/services/categorization-and-ai-services.md)).
- **Deterministic `source_key`**: goal-service dedupes `budget.month_closed` on a
  deterministic key backed by a unique constraint
  (`goal_allocation_history (source_key, goal_id)`) — idempotency guaranteed by the
  schema, not by application logic.

## 2. Self-healing full-state events

Events carry **full state**, not deltas (e.g. `category.*` events carry the whole
category). Consumers upsert, so a missed or reordered event is healed by the next one.
This is why taxonomy read-copies and the ES projections stay consistent without replay
tooling. See [read-copies-and-denormalization](read-copies-and-denormalization.md) and
the projection consumer in
[cqrs-es-read-store](cqrs-es-read-store.md).

## 3. DLQ + retry

**Best-in-repo**: goal-service's `budget_month_closed_consumer`
(`services/goal-service/app/workers/budget_month_closed_consumer.py`) — own queue, DLQ,
header-based retry counting. analytics-service's consumers follow the same shape with
per-queue DLQs (`projection_consumer.py`, `embedding_consumer.py`), and the
categorization feedback consumer copied that wiring (F1-03,
[plans/2026-07-17-user-rules-and-feedback-loop.md](../plans/2026-07-17-user-rules-and-feedback-loop.md)).

**Isolation rule** (decision
[2026-07-13-embed-worker-placement](../decisions/2026-07-13-embed-worker-placement.md)):
a consumer with a slow/flaky dependency (Ollama) gets its **own queue + DLQ** so it cannot
back up the queue that keeps core projections fresh. Bind both to the topic exchange;
don't share a queue across concerns.

## Anti-patterns observed (audit; some still open)

- **Retry by republishing to the topic exchange** → the retry fans out to *all*
  subscribers, not just the failing consumer (transaction-service, MEDIUM).
- **`json.loads` outside try** → malformed message = poison loop.
- **prefetch=1 + inline `sleep`** → head-of-line blocking.
- **Silently dropping messages on failure** (account-service `user.created` consumer: no
  DLQ, no requeue → default account never created, HIGH).
- Unit-testing the handler is **not** the same as a working event path — wire-through
  tests with real UoW required; see memory/exam note and the wave-B lesson in
  [sessions/2026-07-15-phase2-wave-b-resume.md](../sessions/2026-07-15-phase2-wave-b-resume.md).
