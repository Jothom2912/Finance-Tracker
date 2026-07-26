---
date: 2026-07-26
topic: P1-14 — the transactions page pages the whole period, with an honest total
---

# Session 2026-07-26 — P1-14: the transactions page gets a total it can be held to

Third of three in a chain that all had the same shape. [P1-13](2026-07-25-p113-budget-spend-from-analytics.md)
found that budget-service summed at most 50 transactions;
[P3-20](2026-07-26-p320-cleanup-script-outbox.md) found that the read model it now trusts had a
phantom row; this one fixes the surface the user actually reads, where the same 50-row ceiling
had been hiding 46% of June.

## Done

**P1-14 shipped in 12 commits.** Full detail per step in the
[plan](../plans/2026-07-26-p114-transaction-list-pagination.md); the shape question is its own
[decision note](../decisions/2026-07-26-transaction-list-envelope.md).

The ordering is the part worth reusing: **the frontend's tolerant reader landed in step 6, the
server's breaking envelope in step 11.** Between them, pagination already worked (the old
server honoured `skip`/`limit`) with an approximate total. There was no deploy window in which
an old bundle met a new shape — not because a shim mitigated it, but because the sequence made
it impossible. The cost was one dead branch, filed as P3-36 in the same commit that introduced
it rather than left to memory.

| Measured against the rebuilt container | `total_count` | items | Postgres |
|---|---|---|---|
| June 2026 | **93** | 50 | 93 |
| July 2026 | 62 | 50 | 62 |
| April 2026 | 50 | 50 | 50 |

June's two pages partition the set exactly (50 + 43 = 93, disjoint) and **both report 93** —
the total describes the set, not the window. `limit=201`/`limit=0`/`skip=-1` now 422 where they
returned **500** before. The listed expenses sum to 16 709,83, which is what analytics reports
to the øre. **UI confirmed by the user** at `npm run dev`: the pager works, and the page opens
on the current month (July, 62) because that is the default filter — June's 93 is one date
preset away.

**Search was half the finding and got fixed too.** `useTransactionSearch` already accepted
`filters` and already had them in its key; `TransactionsPage` simply never passed them. One
argument. Behaviour change to communicate: with the default filter being the current month,
search now covers that month rather than all history — correct for a visibly active filter
panel, but it will read as a regression to anyone used to global search.

Three items spawned: **P3-36** (remove the tolerant reader), **P3-37** (`transactions` has no
soft-delete column), **P2-30** (the e2e budget-close race below).

## What this session got wrong

**I diagnosed data drift instead of reading the log of the change that caused it.** The plan's
Done-when named 16 739,83 for June; the live stack said 16 709,83. My first written explanation
— committed in `41747a6a` — was that a row had been hard-deleted and could not be inspected,
since `transactions` has no soft-delete column. Wrong. The answer was in
[the cleanup-script finding](../findings/2026-07-25-cleanup-script-desyncs-read-model.md),
written **this morning, by me**: `cleanup_pg_duplicates.py` deleted tx **864, 30,00**, a real
duplicate, and P3-20 reconciled ES for June from 85 / 16 739,83 to 84 / 16 709,83. P1-13 had
measured against the read side while it still held that duplicate.

A `grep` for `16 709` would have found it in one call. The reflex that failed is specific and
worth naming: when a number moves, **look for the commit that moved it before theorising about
the mechanism** — especially in a repo where every such change leaves a finding behind. Corrected
in the plan, the finding and P3-37's justification; the wrong version stays in `41747a6a`'s
message, which is why the correction is written down rather than quietly applied.

**Two numbers in the plan were inherited rather than measured**, and that is the same failure at
one remove. The Done-when copied P1-13's literal; July's "61" was a row count that a
transaction created at 17:15 today turned into 62. A target number lifted from an earlier plan
inherits that plan's snapshot of a live dataset and stops being a contract the moment the data
moves — a *reconciliation* survives that, a literal does not.

## Also found

**The E2E job has been red on master since before P1-14** (`e2b38207`, 2026-07-25 22:58), and
three `test_budget_month_closed_e2e.py` tests fail locally the same way: the close allocates the
whole 5 000 budget where 2 000 is expected, i.e. spend read as **0**. Not on P1-14's path —
since P1-13 budget-service reads spend from `analytics/overview`, and the only two callers of
the transaction list are the frontend and analytics' backfill. Verified it is timing, not loss:
the test's three expenses do reach ES (9 hits for `"E2E expense"`, 3 000,00 per user across
three runs) and `/overview` reports 3 000,00 afterwards. The test polls for the *allocation* but
not for the *spend* it depends on — a synchronous-write assumption left behind when P1-13 moved
spend to an async read model. Filed as **P2-30**, not fixed here.

## Notes for next time

*   **`make test-e2e` does not run locally.** `uv run pytest` in the repo root has no
    environment — there is a `pytest.ini` but no `pyproject.toml`, and CI `pip install`s pytest
    globally. Worked around with `uvx --with pytest-asyncio --with httpx --with requests --with
    python-jose pytest tests/e2e -m e2e`. The Makefile target is misleading as written.
*   **A termination guard cannot be mutation-checked by "which test goes red".** Deleting either
    of the backfill's two stop conditions makes the suite *hang*, not fail. The honest report is
    "the suite no longer terminates", and a test pinning one guard must leave another standing —
    which is why the new `total_count` test has its stub stop producing new ids after three
    pages.
*   **`userEvent` is not the convention here** and RTL 14 does not act-wrap it; every stateful
    interaction printed "not wrapped in act". `fireEvent` is what the repo uses.
*   **Secrets in verification.** The measurement ran *inside* the container so `JWT_SECRET` never
    reached the transcript — the permission layer rejected `printenv JWT_SECRET`, correctly, and
    minting the token where the secret already lives is both safer and less work.
