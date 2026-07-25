---
date: 2026-07-25
topic: closing the loose ends left by the notification-hardening and P2-22 waves
---

# Session 2026-07-25 — loose-ends cleanup

Scope chosen deliberately: **cleanup and documentation only, no code changes.** Three
findings were written up and given backlog IDs; nothing was fixed. Two of the three had
never been recorded anywhere, and one of those was found while looking for the others.

## Done

**Dev-environment artefacts removed** — the `p222-smoke` trio from the P2-22 live
verification, deleted in reverse dependency order after confirming the chain:

| Store | Row | Note |
|---|---|---|
| `postgres-notifications.notifications` | `019f9b21-130f-70de-83c6-09fb42467293` | *"2 transaktioner blev importeret."* — the 2 transactions never existed |
| `postgres-banking.outbox_events` | `15b82966-…`, correlation `bbcb506c-…` | committed at the same microsecond as the inbox row — incidental re-confirmation that P2-22's guard writes atomically |
| `postgres-banking.processed_events` | `p222-smoke-1785014050:mark_sync_complete` | the only row in the table |

Counts afterwards match the "før" column of the P2-22 session log exactly (outbox
`bank.sync.completed` 23, `processed_events` 0, notifications back to the pre-smoke set),
so the cleanup removed the test's footprint and nothing else. The three legitimate
notifications from the F2-03 and hardening runs were left in place.

**Two DLQs purged**, both empty afterwards; no queue in the broker now holds a message.

- `saga_service.saga_start.dlq` — 3 × `saga.bank_sync.start` from **2026-07-16**, rejected
  three times each. Nine days old with nothing since, i.e. debris from the P2-09 session,
  not a live failure.
- `transaction_service.transaction_categorized.dlq` — 1 message from **today 17:12**. Read
  before purging; it was not debris (below).

**Three findings written, three backlog items opened**: P1-13, P2-25, P3-19.

## Learned / surprised

**The DLQ message was a real bug, and the DLQ was the only place it was visible.**
Traced: `categorization-transaction-consumer` categorized tx 1133 at 17:12:01 and emitted
`transaction.categorized`; the write-back consumer then retried five times over 33 seconds
and dead-lettered. `select … where id between 1128 and 1140` shows 1133 as a gap in an
otherwise dense sequence — the row was created, categorized, and deleted while the event
was in flight. Root cause is that transaction-service **hard-deletes** (no `deleted_at`
column, against CLAUDE.md's own anti-pattern list), which makes "not committed yet" and
"gone for good" the same observation, so `_TransactionNotFoundYet` cannot distinguish them.
→ [finding](../findings/2026-07-25-transaction-hard-delete-categorized-dlq.md), P2-25.

**budget-service has been computing spend from 50 transactions.** Found by reading the port
while answering "what should we do next", not by any failure. `TransactionPort` sends no
`limit`; transaction-service defaults to 50 and applies it after `ORDER BY date DESC`.
Quantified against the dev DB rather than argued:

| Period | Tx | Seen | True spend | Computed | Understated |
|---|---|---|---|---|---|
| account 1, June 2026 | 94 | 50 | 16 739,83 | 5 180,32 | 69% |
| account 1, July 2026 (**open** budget) | 61 | 50 | 17 528,17 | 10 286,17 | 41% |

The sharp part is where it lands: `close_month` derives surplus from this number and
allocates the surplus to a goal, and it is *explicitly* fail-closed against a fictional
surplus arising from `spent=0`. Truncation produces the same fictional surplus partially
and without raising, so the guard it was given never fires. F2-03's alerts, shipped five
days ago, evaluate thresholds against the same truncated figure.
→ [finding](../findings/2026-07-25-budget-spend-truncated-at-50.md), P1-13.

**Filed as P1 even though Phase 1 was declared complete on 2026-07-07.** The P1 table's
admission rule is money-corruption, which is a property of the defect, not of the date it
was found. Filing it in P2 for tidiness would have made the severity a function of
discovery order. A note under the phase header records the reasoning.

**A finding recorded only inside a completed plan is effectively unrecorded.** The
non-UUID-`saga_id` poison gap was written down this morning — as a paragraph in P2-22's
Outcome section. It was not in the backlog and had no finding, and it would not have been
found again except by re-reading a plan marked done.
→ [finding](../findings/2026-07-25-saga-reply-non-uuid-poison.md), P3-19.

**Small test accounts hide the truncation bug perfectly.** Every e2e run so far has used
accounts with well under 50 transactions per month, which is exactly the range where the
port returns the right answer. The bug needs an *ordinary* account to appear.

## Open ends

- **P1-13 is the next piece of work** and needs a plan first. Direction in the finding:
  point budget-service at analytics-service's canonical rules (ADR-0004) rather than
  raising the limit, which also removes the `category_id is None` and `type == "expense"`
  divergences in the same port. Accepted trade-off is eventual consistency on spend;
  `close_month` must stay fail-closed against the new upstream.
- **P2-25 needs the soft-delete decision before the consumer fix**, in that order — the
  guard cannot be written while the two states are indistinguishable. The migration reaches
  the P2-09 dedup key, all read paths, the ES projection and analytics aggregations.
- **Still no login helper in `scripts/`**, so no real end-to-end bank sync has ever been
  observed; every live verification so far has built its own synthetic setup and therefore
  proved less than it appears to. Unchanged by this session.
- Carried forward untouched: P2-21, P2-23, P2-24, P3-17, P3-18, P2-15.
- `dismiss` is still non-idempotent by accepted decision (double-click → 404); awaiting a
  frontend complaint before revisiting.

## Notes updated

- Created `findings/2026-07-25-budget-spend-truncated-at-50.md`,
  `findings/2026-07-25-transaction-hard-delete-categorized-dlq.md`,
  `findings/2026-07-25-saga-reply-non-uuid-poison.md`
- `backlog/BACKLOG.md` — added P1-13, P2-25, P3-19 + a note on the P1 admission rule
- `00-INDEX.md` — three finding lines + this session
