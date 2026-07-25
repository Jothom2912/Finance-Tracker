---
title: cleanup_pg_duplicates.py deletes behind the outbox and leaves phantom rows in the ES read model
date: 2026-07-25
severity: MEDIUM
area: transaction, analytics, tooling
status: resolved
resolved-by: plans/2026-07-26-p320-cleanup-script-outbox.md
---

# cleanup_pg_duplicates.py deletes behind the outbox and leaves phantom rows in the ES read model

**Where**: `scripts/cleanup_pg_duplicates.py:144-153`.

**Defect**: The script deletes straight from the write database:

```python
cur.execute("DELETE FROM transactions WHERE id = ANY(%s)", (ids,))
```

No `TransactionDeletedEvent`, no outbox row. The service's own delete path
(`services/transaction-service/app/application/service.py:277-299`) writes the event and
the delete in one transaction precisely so the read side learns; the script bypasses that
contract while operating on the same table.

The script is otherwise careful — dry-run by default, `--execute` required, FK checks
before deleting, every removed row logged as JSON for audit. That care is what makes the
gap easy to miss: it looks like a safe tool, and it is safe with respect to the write
model. It is the *read* model it silently corrupts.

**Why it matters**: Found by measurement, not by reading. Comparing analytics' answer for
account 1 / user 1 against Postgres for July 2026:

| Source | Live expense rows | Sum |
|---|---|---|
| Postgres (truth) | 53 | 17 528,17 |
| Elasticsearch | 54 | 17 666,17 |

The extra row is transaction **1119** (`amount 138.00`, `"Aisha ApS"`, `tx_date 2026-07-24`),
present in `transactions_v2` with `is_deleted: false` and absent from Postgres. Nothing will
ever remove it: the row that would have triggered the delete event is already gone, so no
retry, backfill-from-events or self-healing consumer can notice. Only a full reindex from
the write model would.

Diffing the two id sets for that period showed exactly one phantom and **zero** rows missing
in the other direction, so ordinary projection is healthy — this is a one-way leak caused
by out-of-band writes, not projection lag.

The impact is now larger than when the script was written. Under
[P1-13](2026-07-25-budget-spend-truncated-at-50.md) budget-service starts reading spend from
this read model, so a phantom row inflates the month-close surplus and the F2-03 alert
thresholds. 138 kr on ~17 500 is 0,8% — negligible against the 41% error P1-13 removes, but
it is permanent, silent, and grows by one row per out-of-band cleanup.

**Suggested fix**: The script must go through the same contract as the service. Two options,
in preference order:

1. **Write the outbox row in the same transaction as the delete** — mirrors
   `delete_transaction`, keeps the existing publisher doing the work, and needs no new
   infrastructure. The script already runs `SELECT` + `DELETE` in one transaction
   (documented at line 14), so the insert has a natural home.
2. **Call transaction-service's delete API instead of touching the DB** — most correct, but
   needs auth and turns a maintenance script into a service client.

Whichever is chosen, add the general rule somewhere durable: *scripts that write to a
service's database are participants in its event contract, not observers of it.* This is
the only such script today, but `scripts/` also holds a backfill and other data tools.

Reconciling the existing drift is separate and cheap here (one row). A general
"reindex `transactions_v2` from Postgres" path would be the honest answer if the count ever
grows — worth considering alongside P2-25's soft-delete decision, since soft-delete would
make this class of leak detectable by comparing counts rather than diffing id sets.

Tracked as P3-20.

---

## Resolved 2026-07-26

Fixed by option 1 as recommended — the outbox row is now written in the script's existing
transaction ([plan](../plans/2026-07-26-p320-cleanup-script-outbox.md), commit `b0a9c2b7`).
The durable rule landed in
[patterns/transactional-outbox.md](../patterns/transactional-outbox.md).

**Two corrections to what is written above.**

**"Reconciling the existing drift is separate and cheap here (one row)" was true only
because the finding diffed one month.** A full id-set diff found **67** phantoms, not one.
66 of them turned out to have a different cause entirely — `ai-service/tests/eval/es_seed.py`
seeding fixtures directly into the production index — now filed as
[P3-21](2026-07-26-eval-seed-writes-to-prod-index.md). The P3-20 attribution was correct:
exactly one real-user phantom, exactly the predicted row.

**The drift was measurable in both directions and only leaked one way.** 0 rows present in
Postgres but missing from ES, confirming the original claim that ordinary projection is
healthy.

Measured before → after (account 1, user 1, expenses):

| Period | Postgres | ES before | ES after |
|---|---|---|---|
| July | 53 / 17 528,17 | 54 / **17 666,17** | 53 / **17 528,17** |
| June | 84 / 16 709,83 | 85 / 16 739,83 | 84 / 16 709,83 |
| April | 36 / 9 345,02 | 37 / 9 465,02 | 36 / 9 345,02 |

June and April moved because the fixed script deleted two *real* duplicates still sitting
in the database (id 864 at 30,00 and 1024 at 120,00) — a live demonstration of the bug's
ongoing cost, since running the old script that day would have created two more permanent
phantoms. Real-user phantoms after the work: **0**.

Tx 1119 could not be fixed by the script itself — the row is gone from Postgres, so nothing
finds it. Its delete event was reconstructed from the ES document's own fields and inserted
into the outbox, deliberately *not* patched into ES directly: writing to the read model
behind the event contract is the exact violation being closed.
