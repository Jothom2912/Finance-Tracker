---
date: 2026-07-25
topic: P1-13 — budget-service reads spend from analytics instead of 50 truncated rows
---

# Session 2026-07-25 — P1-13 budget spend from analytics

Continuation of the same day's [loose-ends cleanup](2026-07-25-loose-ends-cleanup.md), which
is where P1-13 was found. Decision → implementation → live verification in one pass.

## Done

**P1-13 shipped in 8 commits** (`9145333d` decision · `fcb70025` port rename · `3bbda8ca`
format · `49acc08a` adapter · `52692f9b` wiring · `39e8611f` import fixup · `e801b861`
compose · `14a6fee2` deletion). Full detail in the
[plan's Outcome](../plans/2026-07-25-p113-budget-spend-from-analytics.md).

The shape: `ISpendPort` with two methods — `get_expenses_by_category` for budget lines and
`get_total_expenses` for the month-close surplus — implemented by `AnalyticsSpendPort`
against `/api/v1/analytics/overview`. The old `TransactionPort` survived until step 6 so the
two could be measured against each other, then was deleted.

| Period | Old | New | Postgres |
|---|---|---|---|
| June 2026 | 5 180,32 | **16 739,83** | 16 739,83 |
| July 2026 | 10 286,17 | **17 666,17** | 17 528,17 |

Live: fail-closed holds (analytics stopped → summary 200/`spent=0`, close 503, `closed_at`
NULL, 0 outbox rows); F2-03 emitted 7 events for account 1, 5 deduped on `source_key`, 2 new
notifications — both 100%-crossings that truncated spend could never reach. 117 tests green,
four mutation checks.

**Two findings written and one retracted** — see below.

## Learned / surprised

**Query the running system before writing the adapter, not after.** Hitting
`/api/v1/analytics/overview` from inside the budget container took one command and returned
16 739,83 — the exact Postgres figure. That single call confirmed the canonical rules, ES
sync, the auth path and the response shape before a line of adapter code existed, and turned
the verification targets from predictions into measurements. It also caught the phantom row
(below), which a post-hoc verification would have read as "close enough".

**A committed finding of mine was wrong, and chasing a 138 kr discrepancy is what exposed
it.** P2-25 claimed every downstream projection shared the categorization consumer's
blind spot for deleted transactions. It does not: `delete_transaction` writes a
`TransactionDeletedEvent` to the outbox in the same transaction, and ES honours it via an
`is_deleted` field — five correctly-flagged July rows, plus tx 1133 itself. Retracted in
place, visibly, rather than edited away. The real culprit was
`cleanup_pg_duplicates.py:148` deleting straight from the write DB with no event → P3-20.

**The ES read model can hold rows that nothing will ever remove.** Phantom tx 1119 is live
in `transactions_v2` and absent from Postgres. No retry, no self-healing consumer and no
event replay can fix it, because the row that would trigger the delete event is already
gone. Only a reindex would. Worth remembering as a property of event-sourced read models
generally: they self-heal against *missed* events, not against events that were never
emitted.

**Third red-CI discovery in one day.** budget-service's job had failed `ruff format --check`
since 2026-07-20 (F2-03's commit), and since that step precedes the test step, its 117 tests
had not run in CI for five days either. Same pattern as banking-service and the three shared
packages this morning. Three independent instances in a day is not three mistakes, it is a
missing feedback loop — nobody watches CI and `make check` is not run before commit.

**A pipe hides the exit code.** `uv run ruff check . 2>&1 | tail -2 && git commit` commits
even when ruff fails, because the pipeline's status is `tail`'s. Cost one fixup commit.

**Testing fail-closed on real data is a bet on the thing you are testing.** Closing the real
open July budget to prove it *would not* close would have credited a fictional surplus to a
goal if the guarantee were broken. Used a throwaway budget row instead, deleted afterwards.

## Open ends

- **P3-20** — `cleanup_pg_duplicates.py` deletes behind the outbox. One phantom row exists
  today (138,00 on account 1 / July); it inflates budget numbers now that budget-service
  reads that model.
- **P2-25** — transaction soft-delete decision still pending; the corrected finding narrows
  the blast radius but does not change the recommendation.
- **CI is unwatched.** Three services found red in one day by accident. The fix is a
  mechanism (pre-commit hook, or actually looking at Actions), not another `ruff format`
  commit. Not yet a backlog item — needs a decision on which mechanism.
- **Historical closed months keep their too-high surplus**; goal `amount_saved` credited from
  them is not retro-corrected. Recorded in the decision, deliberately not reconciled.
- The two new July notifications are legitimate crossings and were left in place.
- Unchanged: P2-21, P2-23, P2-24, P3-17, P3-18, P3-19, P2-15, and the missing login helper
  for real end-to-end bank-sync verification.

## Notes updated

- Created `decisions/2026-07-25-budget-spend-from-analytics.md`,
  `findings/2026-07-25-cleanup-script-desyncs-read-model.md`, this session log
- `plans/2026-07-25-p113-budget-spend-from-analytics.md` → `status: done` + Outcome
- `findings/2026-07-25-budget-spend-truncated-at-50.md` → `status: resolved`
- `findings/2026-07-25-transaction-hard-delete-categorized-dlq.md` → retraction added
- `backlog/BACKLOG.md` — P1-13 done, P3-20 added
- `architecture/services/account-budget-goal-services.md` — spend source + fail-open/closed
  policy rewritten
- `00-INDEX.md`
