---
title: Deleted transactions send the categorization write-back to the DLQ
date: 2026-07-25
severity: MEDIUM
area: transaction
status: open
backlog: [P2-25]
resolved-by: null
---

# Deleted transactions send the categorization write-back to the DLQ

**Where**: `services/transaction-service/app/adapters/outbound/postgres_transaction_repository.py:116-126`
(the hard delete) and `services/transaction-service/app/workers/categorized_consumer.py:74-76`
(the consumer that cannot tell the two cases apart).

**Defect**: Two problems that only bite in combination.

1. **transaction-service hard-deletes.** `TransactionRepository.delete` does
   `await self._session.delete(model)`, and the `transactions` table has neither
   `deleted_at` nor `is_deleted` (verified against the live schema). CLAUDE.md lists
   "Hard-deletes på domain-entiteter" under anti-patterns to avoid, and goal-service was
   migrated to soft-delete in P3-16 — transactions, the most audit-relevant entity in the
   system, were not.

2. **`_TransactionNotFoundYet` conflates two states.** Categorization is asynchronous, so
   the write-back consumer legitimately races the insert and retries with backoff. But the
   same exception is raised when the row is *gone for good*:

   ```python
   tx = await self._get_transaction(session, transaction_id)
   if tx is None:
       await self._stale_backoff(message, transaction_id)
       raise _TransactionNotFoundYet(transaction_id)
   ```

   The handler already imports and uses `PoisonMessageError` (line 66, for a missing
   `transaction_id`), so the reject-immediately mechanism exists — it just is not reachable
   from this branch. And with a hard delete there is no way to reach it: "not yet" and
   "never again" are the same observation.

**Why it matters**: Observed, not hypothetical. On 2026-07-25 at 17:12,
`transaction_service.transaction_categorized.dlq` received one message, traced end to end:

- 17:12:01 — `categorization-transaction-consumer` logs
  `Categorized transaction 1133 -> cat=8, sub=32, tier=fallback [low]` and emits
  `transaction.categorized` (correlation `ed06c91f-…`). The event exists, so the row had
  committed.
- 17:12:03 → 17:12:34 — `transaction-categorized-consumer` retries five times with
  1/2/4/8/16 s backoff, each `Transaction 1133 not found yet`, then DLQs.
- `select … where id between 1128 and 1140` — 1133 is a gap in the sequence; 1128–1132 and
  1134–1137 are all present. The row was created, categorized, then deleted mid-flight.

The cost is moderate and mostly diagnostic: no data is corrupted (the row is gone; there is
nothing to write back), but every deleted-while-categorizing transaction burns five
retries with backoff on a shared consumer and leaves a message in a DLQ that reads like an
unexplained failure. A DLQ that accumulates benign entries stops being a signal — which is
precisely why this one sat unexamined until someone went looking.

**Correction (2026-07-25, same day):** an earlier revision of this finding claimed that
"any downstream projection keyed on a transaction id has the same blind spot". That is
**wrong** and is retracted. `TransactionService.delete_transaction`
(`app/application/service.py:277-299`) emits a `TransactionDeletedEvent` to the outbox in
the same transaction as the delete, and the ES read model consumes it — `transactions_v2`
carries an `is_deleted` boolean, and live inspection found five correctly-flagged July rows
plus tx 1133 itself marked `is_deleted: true`. The event path is intact.

The blind spot is narrower than stated: it is *this consumer*, which reads the row rather
than the event and therefore cannot see a deletion that has already happened. The missing
audit trail inside transaction-service's own database stands.

A separate, genuinely unguarded delete path does exist — see
[the cleanup-script finding](2026-07-25-cleanup-script-desyncs-read-model.md) — but it is a
maintenance script, not the service.

**Suggested fix**: Two steps, in order.

1. **Decide soft-delete for transactions** (deliberately deferred, 2026-07-25 — see P2-25).
   This is not a small migration: it touches the P2-09 dedup key, every read path, the ES
   projection and analytics' aggregation rules, all of which currently assume a row's
   absence means it never existed. Plan-first.
2. **Then** let the consumer distinguish the states — a row with `deleted_at` set is a
   `PoisonMessageError` (ack and drop, the categorization is moot), a genuinely absent row
   keeps the existing retry. Doing step 2 without step 1 is not possible without guessing.

Interim option if step 1 stays deferred: cap the damage by treating exhausted retries as
expected rather than exceptional for this specific case, so the DLQ keeps its signal value.
That is a papering-over, not a fix, and should be labelled as such.

Tracked as P2-25.
