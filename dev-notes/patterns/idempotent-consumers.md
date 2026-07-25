---
title: "Pattern: idempotent consumers (inbox, full-state events, DLQ + retry)"
updated: 2026-07-25
source: architecture audit 2026-07-07; embed-worker decision 2026-07-13; P2-22 2026-07-25
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

The table itself is **not** uniform, despite what transaction-service's migration 007
comment claims ("standardised across the platform"). Two live schemas:
`(message_id String(36), consumer_name, event_type)` in transaction- and
categorization-service, `(correlation_id String(255), consumer_name)` in banking-service.
Both work; only the claim of standardisation was wrong. Not worth a migration on a table
existing consumers depend on — just don't copy the comment.

### 1a. Saga commands are the exception — key on `(saga_id, step_name)`

`ConsumerBase`'s `InboxDeduplicator` hook keys on `payload["correlation_id"]`. **That does
not work for saga commands**, and the reason is worth knowing before someone "fixes" a
saga-command consumer by wiring up the standard hook:

- saga-service builds command payloads as plain dicts (`_publish_step_command`) — there is
  no `correlation_id` in the body at all.
- The value it *does* set, on the outbox row, is `saga.correlation_id` — **the same for
  every step of the saga**. Dedup on it would treat step 2 as a duplicate of step 1 and
  stall the saga silently.

The correct key is the saga's natural step identity, `f"{saga_id}:{step_name}"`
(banking-service's `mark_sync_complete` handler, P2-22). It is safe because the
orchestrator never re-issues an *execution* step: `handle_reply` requires `STARTED` plus a
step-name match and then advances, and a timeout goes to **compensation**, not to a step
retry. The one command it does re-emit by itself is `rollback_import`
(`_handle_stale_compensation`), which is idempotent by construction.

Three rules that make such a guard correct rather than merely present:

1. **A deduplicated command must still reply.** The usual *cause* of redelivery is a lost
   reply. Acking without replying leaves the orchestrator waiting until timeout, which then
   compensates — trading a duplicate side effect for a failed saga.
2. **The inbox row belongs in the handler's own transaction.** Commit it separately and
   idempotency costs you retry: a handler that raises after the inbox commit but before the
   effect commit would never run again. In one transaction, "the effects happened" and "the
   command was seen" are the same fact.
3. **A partial key is worse than no key.** Missing `saga_id`/`step_name` must fall back to
   *no* dedup (and say so in the log). Keying on `":"` would make every keyless command
   after the first a duplicate.

**When plain dedup is not enough:** if the reply carries the result (not just a status), a
skip-and-ack guard would answer with an empty result and lose data downstream. Those need
*stored reply* — persist the first reply, resend it verbatim. Two handlers are in that
class today: banking's `bank_fetch_transactions` (reply carries the whole fetch; left
deliberately unguarded) and transaction-service's `bulk_import` (reply carries
`imported_ids`, which the compensation needs → P2-23).

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
