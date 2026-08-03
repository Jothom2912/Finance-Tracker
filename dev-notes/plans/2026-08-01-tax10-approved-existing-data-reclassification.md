---
title: TAX-10 — approved existing-data reclassification execution
date: 2026-08-01
status: done
backlog: [TAX-10]
related:
  - plans/2026-08-01-tax07-existing-data-reclassification-dry-run.md
  - plans/2026-08-01-tax06-additive-taxonomy-migration.md
  - decisions/2026-08-01-taxonomy-semantics-and-identity.md
---

# TAX-10 — approved existing-data reclassification execution

## Goal

Apply the reviewed TAX-07 safe and evidence-backed proposals to the active categorization-,
transaction- and budget-service data through service-owned, idempotent write paths, then let the
normal event pipeline repair Elasticsearch. Completion means every applied row resolves by stable
target key to the active taxonomy, protected/review/unresolved rows remain byte-for-byte unchanged,
database and analytics totals reconcile, and the user can manually exercise the new categories in
the frontend against real data. Execution starts only after this plan and its freshly generated
pre-write approval hash receive explicit owner approval.

## Context

[TAX-07](2026-08-01-tax07-existing-data-reclassification-dry-run.md#outcome-fill-in-when-done)
reconciled 749 transactions and produced deterministic read-only proposals, but explicitly recorded
`writes_authorized=false`; its disposable reports and databases were then correctly removed. The
recorded summary hash is evidence for the completed dry-run, not reusable write input. A real write
therefore needs a fresh snapshot, rerun and approval artifact, optimistic conflict checks and a
separately auditable execution path.

The apparent TAX-07 total of 546 `safe_one_to_one` plus 626 `evidence_proposal` references is not a
blind write count. An executable row must also have a non-null stable `target_key`/public UUID that
is valid in the owning service at execution time. In particular, evidence dispositions emitted by
historical categorization rows do not become writable merely because their disposition is named
`evidence_proposal`. The existing exclusions remain authoritative: 527 unresolved, 7 manual
reviews and 6 protected references are outside this plan.

## Non-goals

- No write to a service's database by another service, and no direct Elasticsearch bulk update,
  reindex or alias swap.
- No mutation of protected manual/gold transaction assignments, user-authored or learned rules,
  budget collisions, unresolved rows, or evidence rows without one allowed resolved target.
- No automatic resolution of the remaining 527 ambiguous transactions or 7 budget reviews.
- No deletion of legacy/deprecated taxonomy rows, integer compatibility fields or old event
  versions; cleanup requires measured zero-reference evidence and a later plan.
- No TAX-08 persona fixtures, TAX-09 quality gate, classifier training or unrelated frontend work.
- No execution against active data merely because this plan exists; approval is bound to the fresh
  pre-write summary hash and the exact candidate manifest generated in step 5.

## Steps

1. [x] **Separate proposals from executable commands.** Extend the shared reclassification
   contract and repository aggregator so an execution manifest contains only rows whose
   disposition is `safe_one_to_one` or `evidence_proposal`, whose `target_key` and public UUID are
   both present and agree with the pinned mapping, and whose source kind is explicitly writable.
   Reject duplicate source identities, a target outside the row's allowed mapping, protected or
   review rows, and evidence dispositions without a resolved target. Add per-service candidate,
   exclusion and reason counts plus a canonical manifest hash; never include raw bank text.
2. [x] **Add service-owned, idempotent writers.** Add application commands and operator CLIs in
   categorization-, transaction- and budget-service. Each command consumes only its own signed-off
   manifest shard, resolves stable target identity to the environment-local surrogate ID through
   its own repository/read copy or existing API port, re-reads the current legacy reference and
   protection tier, and applies bounded batches in transactions. A row already at the requested
   target is a deterministic success; a deleted, changed, protected, missing or no-longer-matching
   row is skipped and reported, never overwritten. `--execute` must additionally require the exact
   approval-summary and manifest SHA-256 values; the default mode remains validation-only.
3. [x] **Preserve categorization ownership and intent.** In categorization-service, update only
   unprotected categorization results and system rules that have a single approved target. Keep all
   user/learned rules and manual/user/gold results unchanged. Resolve both category and subcategory
   from the target semantic key so parent/leaf references cannot diverge; record before/after IDs
   and reason codes without hostile input. Commit through a service-owned unit of work and do not
   emit transaction events for historical result rows.
4. [x] **Migrate transactions atomically with projection events.** In transaction-service, update
   only executable active transaction proposals, resolving target keys against its TAX-06 taxonomy
   read copy. Write category/subcategory/tier fields and the normal self-contained transaction
   update outbox event in the same transaction, preserving manual protection and all financial
   fields. Batch safely, make retry/redelivery idempotent, and prove each committed change produces
   exactly the event needed for analytics to converge. Planned transactions remain protected and
   unchanged under this plan.
5. [x] **Handle only collision-free budgets.** In budget-service, resolve approved category keys
   through its categorization-service port and update only collision-free legacy budgets/monthly
   lines. Preserve amounts, periods and ownership. Any target collision, changed source, unavailable
   target lookup or duplicate target in the same monthly budget is a skip that keeps the entire
   affected budget aggregate unchanged; the 7 TAX-07 reviews are never auto-merged.
6. [x] **Refresh evidence and stop for hash-bound approval.** Take and verify restorable snapshots
   of the three active databases and capture Elasticsearch count/ID/field/group/amount hashes.
   Rerun the three TAX-07 scanners twice at one boundary, aggregate them, generate byte-identical
   candidate manifests, and compare counts/deltas with the completed TAX-07 Outcome. Record drift
   explicitly. Set `writes_authorized=true` only in a separate operator approval file containing
   the newly reviewed summary and manifest hashes; stop before `--execute` until the owner approves
   those exact hashes.
7. [x] **Rehearse, execute and observe convergence.** Restore the fresh snapshots into disposable
   databases, run each writer twice (first apply, second no-op), and verify exclusions, invariants,
   outbox events and Elasticsearch convergence. After approval, execute one service at a time on
   active data with before/after counters and retained audit artifacts. Keep workers running, wait
   for outbox/inbox drain, and require Postgres↔Elasticsearch reconciliation over all active
   transactions before declaring success. Do not manually patch Elasticsearch.
8. [x] **Verify and hand off frontend testing.** Add deterministic unit tests for selection,
   identity resolution, conflict/protection checks and idempotency; integration tests for atomic
   updates/outbox and rollback; aggregator negative controls for altered hashes and broadened scope;
   and a browser/API smoke showing new category/subcategory names on real migrated transactions.
   Run `make -C services/categorization-service test check`,
   `make -C services/transaction-service test check`,
   `make -C services/budget-service test check`, focused analytics projection tests,
   `make compose-check`, `make notes-check` and `git diff --check`. Record exact applied/skipped
   counts, before/after hashes, projection lag and rollback status in Outcome; mark TAX-10 done only
   when frontend-visible data and analytics both reconcile.

## Risks & rollback

- **Stale evidence overwrites newer intent.** Detect by optimistic re-read of the legacy IDs,
  protection tier and source fingerprint captured in the new manifest. Skip drifted rows and rerun
  review; never widen the match predicate to force completion.
- **Stable targets resolve to the wrong local integers.** Resolve key plus public UUID inside each
  owning context and require their pair to match the active TAX-06 registry. Abort the service batch
  on a missing or conflicting pair.
- **Partial multi-service completion.** Services commit independent, idempotent batches and retain
  applied/skipped manifests. Resume forward from the same approved hashes where safe; cross-service
  database access and distributed transactions remain forbidden.
- **Analytics diverges or lags.** Compare transaction write/outbox counts with consumer inbox and
  Elasticsearch hashes. Pause further services, retain audit output and let normal events retry.
  Use a service-owned full-state replay for forward repair; never edit the index directly.
- **Budget lines collapse or totals change.** Treat collision groups atomically and exclude them.
  Verify per-budget periods, line counts and summed amounts before and after every rehearsal/run.
- **Rollback is needed.** Before execution, verify restores on disposable databases. For an active
  incident, stop writers/workers as appropriate and restore all affected service snapshots plus the
  matching Elasticsearch snapshot, or use the retained inverse manifests through the same
  service-owned event-emitting paths. Do not mix a restored write model with a newer projection.
- **Sensitive data enters logs or manifests.** Keep identity, old/new taxonomy references, reason
  and status only; no raw descriptions, credentials or full hostile input. Store approval/audit
  artifacts access-controlled and remove them only after Outcome retains hashes and aggregate facts.

## Active-data approval checkpoint — 2026-08-01

Implementation and disposable rehearsal are complete; active writes remain blocked. Fresh copies
of the active categorization 007, transaction 013 and budget 004 databases were upgraded only in
the disposable scope (categorization via the approved P2-44 bootstrap to 009, transaction to 014)
and scanned twice at boundary `2026-08-01T21:18:00Z`. Both report sets, summaries and execution
manifests were byte-identical. The aggregate still matches TAX-07 exactly: 546 safe, 626 evidence,
527 unresolved, 7 review and 6 protected references with unchanged signed total and traced DKK
630 expense→cash plus DKK 6,700 income→savings.

The executable scope is **556** rows: categorization **307**, transaction **220**, budget **29**.
Excluded are categorization **620** (616 unresolved targets plus 4 non-writable source kinds),
transaction **529** (527 unresolved plus 2 protected) and budget **7** reviews. First writer run
applied 307/220/29; the second produced exactly 307/220/29 `already_applied`. The transaction copy
retains 749 active rows and DKK 582,796.19, has 529 intentionally legacy references, and contains
exactly 220 new target-bearing `transaction.updated` outbox events. Four protected legacy user
rules, 527 unresolved transactions, 2 protected transactions and 7 reviewed budget references
remain unchanged. Budget line count and DKK 203,420 total are unchanged.

Approval summary SHA-256:
`abd5c0f541fcd9d8baf980ff26bdf8cb6affdb075c8406fa5ada65aef10cf623`.
Manifest SHA-256 values: categorization
`c2c8a2acd4418c88a67e8f135504f912742889b5e7682f46c901f417e03d7d29`, transaction
`b865bc12368db9a74449f1cfde2ada3103b1c08a981470e117aea76e367c06a7`, budget
`4227da2fa3472a26eadf2c3d7add3eb70bfa99602dbdeeda1101e588a22430c4`.
Mapping remains
`17c7301ed58447d6add056f002ac21ba0a1253920ac98b2b57040b64dd1e0f24`.

The active databases remain categorization 007, transaction 013 and budget 004; active
Elasticsearch was read only. The three disposable databases, isolated categorization API and
access-controlled report directory are intentionally retained until the owner approves or rejects
this exact checkpoint. Active execution will first re-check these hashes and source boundaries,
apply categorization 007→009 plus transaction 013→014, run the three service writers, allow normal
outbox projection, reconcile Postgres↔Elasticsearch and then remove the disposable resources.

## Precondition re-check — 2026-08-03

Owner approved the checkpoint content on 2026-08-03. A read-only re-check of the retained evidence
and the active databases confirms the approved artifacts and finds three preconditions that the
checkpoint above no longer describes correctly.

Evidence intact. The retained rehearsal directory still hashes to exactly the recorded values:
summary `abd5c0f5…` for both runs, manifests `c2c8a2ac…`/`b865bc12…`/`4227da2f…`, boundary
`2026-08-01T21:18:00Z`, candidate/exclusion counts 307/620, 220/529 and 29/7.

Source data unchanged, so the approved hashes still apply. Active transactions are **749** active
plus 18 soft-deleted (the boundary counted the 749), latest `created_at` is 2026-08-01 16:32 with no
write since, budget is exactly 72 lines/64 monthly/0 legacy, and categorization holds 793 results.
Live `categorization_rules` is **134** (130 system + 4 user); the boundary's 216 is that same 134
plus the 82 constrained rules that exist only after the 009 upgrade, so it is not drift.

Three corrections to the checkpoint:

1. **Transaction is already at 014, not 013.** Migration `014_add_taxonomy_identity_read_copy` has
   been applied to the active database — migration-gated startup ran it. The planned 013→014 step is
   therefore already complete and must not be re-planned as pending work.
2. **The transaction read copy has schema but no identity data.** 0 of 11 categories and 0 of 41
   subcategories carry a `semantic_key`, because the owner is still at 007 and no v3 full-state
   taxonomy event has been emitted. Transaction-service's writer resolves target keys against this
   read copy, so all 220 rows would abort until categorization is upgraded **and** its full-state
   events have drained. This fixes the execution order: categorization 007→009, drain, verify the
   read copy carries 13/67 keys, and only then run the transaction writer.
3. **The stack is not running.** 31 containers are `created` and 10 `exited`; only 26 run. Without
   consumers there is no outbox drain and no Elasticsearch convergence, so step 7's completion
   condition cannot be met until the stack is up and quiesced.

Snapshots were deliberately **not** taken during this re-check: a snapshot taken before the stack
starts would be stale for the write it is supposed to protect. Take them after the stack is up and
quiet, immediately before the first writer.

## Outcome — executed 2026-08-03

Executed against active data after owner approval. Applied **307 categorization + 220 transaction +
29 budget** references — exactly the approved manifest counts — and every writer's second run
returned `already_applied` for the same counts, so idempotency holds on active data and not only in
rehearsal. A negative control confirms the gate is load-bearing: the same command with a wrong
summary hash aborts with `approval does not cover the supplied summary hash` and writes nothing.

Preconditions. Verified custom-format snapshots of all three databases were taken first and proved
restorable in a disposable PostgreSQL 16 container, where they reproduced live exactly: 793/134/007,
749 active + 18 deleted/014, 72/64/004. The categorization migration gate was failing on the P2-44
collision (`Key (id)=(11) already exists`), which had left 31 containers unstarted; the approved
bootstrap installed 008 with `category_start=24 subcategory_start=109` — the same values the
populated-snapshot test pins — and 009 followed. Categorization then held 24 categories (13 keyed),
108 subcategories (67 keyed), 216 rules and 80 allocations. With the stack up, the taxonomy outbox
drained fully (0 pending / 891 published) and the transaction read copy carried 13/67 semantic keys,
which is what made the transaction writer able to resolve targets at all.

Measured drift. Starting the stack ran the bank-sync scheduler, which imported **14 new
transactions**. They were categorized straight into the new taxonomy (e.g. subcategory 139/164) and
have **zero overlap** with the approved 220-row manifest, so the approved hashes still applied
unchanged. The consequence is that the reconciliation target is **763** active transactions, not
P3-21's 749. The next scheduled sync is 24h out, so the boundary held still during execution.

Applied state. Categorization results moved 793→579 legacy and 14→228 new; system rules 134→41
legacy and 82→175 new. That is 214 results + 93 rules = **307**, with all **4** user rules untouched.
Transactions moved 749→**529** legacy, which is exactly the 527 unresolved plus 2 protected rows, and
14→234 new; 763 active rows and DKK **603,760.78** are unchanged by the remap. The outbox holds
**223** `transaction.updated` events (3 pre-existing + 220), all published. Budget lines moved
72→43 legacy + 29 new at an unchanged 72 lines and DKK **203,420.00**, leaving the 7 reviews alone.

Convergence. Every queue and all three outboxes drained to zero. The reconciler exited **0** with
763↔763, no missing/extra IDs, no field mismatch, no group mismatch and
`postgres_hash = elasticsearch_hash = df62af48f5cf9b00c238be9a9f73acc23005bf425cf1e0ca8bd575a7fb814322`,
`report_hash = db2c7ab5874b485e4f9df19beb6e7adf75878461fe665b45423215feee808423`. Frontend-visible
data checks out: migrated transaction 827 now reads category 26 `Transport` / subcategory 119
`Offentlig transport` in the read model. Elasticsearch was never edited directly.

Verification. categorization **188**, transaction **82 integration + 221 unit**, budget **56**,
analytics **124**, `check` (ruff + format + mypy) green for all four, `compose-state-check` 64
containers with nothing dead or restarting, plus `notes-check` and `git diff --check`. Rollback was
not needed and was never invoked; the verified pre-write snapshots are retained under
`/private/tmp/tax10-active-20260803` (mode 700) with the approval file
`bb0dbb1fb27a0662792bf3602fde35c7cb7220b3815501b4421ed1ebe9c47693` until the owner has exercised the
new categories in the UI.

The 527 unresolved transactions, 7 budget reviews and 6 protected references are untouched by design
and remain the open scope. Legacy taxonomy rows and integer compatibility fields were not removed;
that still needs measured zero-reference evidence and a separate plan.
