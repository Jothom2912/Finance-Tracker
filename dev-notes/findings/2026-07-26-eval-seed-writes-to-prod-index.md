---
title: ai-service's eval seed writes 66 fixture documents into the production ES index
date: 2026-07-26
severity: LOW
area: ai, analytics, tests
status: resolved
backlog: [P3-21]
resolved-by: ../plans/2026-08-01-p321-elasticsearch-eval-isolation-and-reconciliation.md
---

# ai-service's eval seed writes 66 fixture documents into the production ES index

**Where**: `services/ai-service/tests/eval/es_seed.py:63`.

**Defect**: The eval harness seeds synthetic transactions straight into
`transactions_v2` — the same index analytics-service projects real transactions into and
budget-service now reads spend from ([P1-13](../decisions/2026-07-25-budget-spend-from-analytics.md)).
The documents are written with `is_deleted: False`, so they are indistinguishable from
live projected rows by every query predicate the read side uses.

**How it surfaced**: while verifying [P3-20](2026-07-25-cleanup-script-desyncs-read-model.md)
I diffed the *full* Postgres/ES id sets rather than the single month the original finding
examined. The result was 67 phantom documents, not the one expected:

| Group | Count | Cause |
|---|---|---|
| tx 1119 | 1 | cleanup script deleting behind the outbox (P3-20 — now fixed) |
| 9000001–9000901 | 66 | this finding |

Profile of the 66: `user_id` 9001 (64 docs) and 9002 (2 docs), `account_id` 1 and 2,
`tx_date` spread over 2026-03 … 2026-05, summing to 16 577,40.

**Why it is LOW and not higher**: every read path filters on `user_id`, and 9001/9002 are
synthetic users with no rows anywhere else in the system. Real users' analytics, budgets
and alerts are unaffected — verified by the same diff, which shows **zero** real-user
phantoms after P3-20. The severity is about hygiene and about the next person to run that
id-set diff, who will find 66 unexplained documents and have to re-derive this.

**Why it still matters**:

1. **The index is shared with production data.** The tenant filter is the only thing
   keeping the fixtures out of real aggregations. Any future query that aggregates across
   users — a system-wide dashboard, an ops metric, a reindex-and-compare — silently
   includes them.
2. **It defeats drift detection.** A Postgres↔ES id-set diff is the natural way to detect
   exactly the P3-20 class of leak. With a permanent floor of 66 unexplained phantoms, the
   check cannot be automated into a "must be zero" assertion — which is what would have
   caught tx 1119 the day it happened rather than three weeks later during an unrelated
   money-correctness fix.
3. **Nothing removes them.** Same terminal property as P3-20: they were never projected
   from a write model, so no event, replay or consumer will ever clean them up.

**Suggested fix**: seed into a dedicated index (`transactions_eval_v2`) with the eval
harness pointed at it via the alias/index name it already resolves, or delete the fixture
documents in the harness's teardown. The first is preferable — it makes the isolation
structural rather than dependent on teardown running.

Once the floor is zero, add the id-set diff as an assertion: **live ES documents minus
Postgres rows must be empty.** That converts the P3-20 class of bug from
"found by accident during an unrelated investigation" into a check.

Tracked as P3-21.

Resolved 2026-08-01 by the
[P3-21 isolation and reconciliation plan](../plans/2026-08-01-p321-elasticsearch-eval-isolation-and-reconciliation.md#outcome-fill-in-when-done):
fixtures now seed only the guarded `eval_transactions` alias, the 66 fixtures plus one classified
orphan were removed from the live index, and the id-set diff shipped as the reusable reconciler that
measured 749↔749.
