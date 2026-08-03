---
title: P2-44 — TAX-06 collision-safe surrogate-ID repair
date: 2026-08-01
status: done
backlog: [P2-44]
related:
  - ../findings/2026-08-01-tax06-migration-collides-with-existing-category-ids.md
  - 2026-08-01-tax06-additive-taxonomy-migration.md
  - 2026-08-01-tax07-existing-data-reclassification-dry-run.md
  - ../decisions/2026-08-01-taxonomy-semantics-and-identity.md
  - ../patterns/read-copies-and-denormalization.md
  - ../decisions/2026-08-01-p244-pre008-bootstrap.md
---

# P2-44 — TAX-06 collision-safe surrogate-ID repair

## Goal

Make TAX-06 deployable from revision 007 on the measured populated snapshot without changing or
deleting any existing taxonomy row or reference. The repaired rollout must allocate new integer
surrogates outside all occupied/reserved ranges while retaining the approved 80 pinned UUIDv7 and
semantic-key identities, converge clean and populated databases on equivalent canonical taxonomy
state, and leave a normal forward Alembic head. Completion requires a byte/row-level before/after
proof against a fresh copy of the failing snapshot, including foreign-key references, sequences,
outbox payloads and downstream read-copy identity.

## Context

The [finding](../findings/2026-08-01-tax06-migration-collides-with-existing-category-ids.md)
records that published migration 008 assumes category IDs `11..23` and subcategory IDs `42..108`.
The copied database has already allocated category ID 11, so its transactional 007→008 upgrade
rolls back before TAX-06 activation. Clean-install tests did not exercise this runtime-allocation
shape.

There is a revision-graph constraint that the repair must not hide: a new revision after 008 cannot
unblock a database at 007, because Alembic executes 008 before it can reach that revision. Likewise,
renumbering the existing category 11 would change an already published integer identity and would
require coordinated consumer repair. The approved implementation must therefore pair an explicit,
idempotent pre-008 bootstrap for the blocked 007 shape with a forward-only post-008 revision that
records and enforces the repaired allocation. This is an operator-gated exception, not an edit to
published migration 008. If review requires a migration-only path with no bootstrap phase, stop:
that requirement conflicts with preserving 008 unchanged and needs a superseding migration-history
decision before implementation.

## Non-goals

- No bulk reclassification or rewrite of transactions, categorization results, budgets, planned
  transactions, user/learned rules or analytics groupings; that still requires its own approved
  write plan after TAX-07.
- No renumbering, deletion, reuse or semantic reinterpretation of any existing category,
  subcategory, merchant, rule or cross-service read-copy identity.
- No changes to the 13/67 taxonomy, the 82 constrained rules, pinned UUIDv7 values, semantic keys,
  event v3 contract or taxonomy ownership.
- No Elasticsearch fixture cleanup or TAX-07 approval packet; P3-21 and the TAX-07 plan retain
  those scopes after P2-44 is proven.
- No mutation of active developer or production databases. All discovery and drills use fresh,
  disposable copies until a separate rollout approval names an environment.

## Steps

1. [x] **Capture and pin the failing 007 shape.** Add a sanitized, deterministic populated-upgrade
   fixture builder under `services/categorization-service/tests/migrations/` that reproduces the
   measured schema revision, occupied category/subcategory IDs, sequence positions and every local
   foreign-key edge from `subcategories`, `merchants`, `categorization_rules` and
   `categorization_results`. Record hashes and exact pre-upgrade row/reference histograms from a
   fresh disposable snapshot copy; do not commit user data. Add a negative control proving current
   008 fails on category 11 and rolls back schema, data and outbox atomically.
2. [x] **Implement an idempotent pre-008 allocation bootstrap.** Add a narrowly scoped owner-side
   operator command under `services/categorization-service/app/tools/` that only runs at revision
   007, takes an explicit run ID, locks the two taxonomy tables for allocation, and reserves two
   contiguous collision-free ranges above the maximum of occupied IDs, sequence values and the
   published 008 ranges. It must persist the chosen 13 parent and 67 child surrogate mappings in a
   migration-owned repair ledger and make no edits to existing rows or foreign keys. A repeated run
   ID must return the identical allocation; a different result or partially populated ledger fails
   closed. Because unchanged 008 cannot consume such a ledger by itself, the command may execute
   only the reviewed bootstrap SQL necessary to install 008's additive schema/seed/outbox state
   with those allocated integers, then stamp 008 only after all 008 postconditions match in the
   same transaction. Do not copy data through application repositories or cross service boundaries.
3. [x] **Add the forward repair revision after 008.** Create
   `services/categorization-service/migrations/versions/009_...py` with `down_revision = "008"`.
   It must adopt/validate the repair ledger for bootstrapped databases, backfill the deterministic
   ledger for clean databases already upgraded by original 008, enforce uniqueness/completeness of
   all 80 UUID/key→surrogate mappings, synchronize both sequences above the true maxima, and reject
   any UUID/key drift, target references outside the ledger, partial TAX-06 state or duplicate
   canonical identity. Its upgrade is additive and idempotent in effect; downgrade removes only
   unused repair metadata and must fail closed once later revisions or target references exist.
4. [x] **Prove reference and identity preservation.** Extend real-Postgres migration tests to cover
   clean 001→head, clean 007→bootstrap→head, the exact populated snapshot shape, occupied IDs inside
   both original ranges, sequences ahead of table maxima, interrupted bootstrap rollback and repeat
   invocation. Compare ordered hashes of every pre-existing row and every FK edge before/after;
   assert only new TAX-06 rows, schema objects, ledger rows and deterministic outbox events appear.
   Assert 13/67 active targets, 10/41 plus runtime-created legacy rows preserved, 82 active target
   rules, zero orphans, collision-free sequences, and exact reuse of all pinned UUIDs/keys.
5. [x] **Verify event/read-copy convergence without semantic writes.** On disposable
   categorization, transaction and Elasticsearch copies, publish the repaired 80-event snapshot
   twice with one run ID. Prove deterministic IDs/payloads, inbox/outbox idempotency, identical
   UUID/key hierarchy in owner and consumers, and no transaction category/subcategory change.
   Compare transaction counts and amount aggregates before/after. This proves P2-44 only; the
   separate 749↔749 transaction-document reconciliation remains P3-21/TAX-07 work.
6. [x] **Document the operator gate and rollback/forward repair.** Add exact preflight, backup,
   bootstrap, Alembic, verification and abort commands to the P2-44 plan Outcome/runbook material.
   Detection must include current revision, ledger hash, occupied ranges, FK/orphan queries,
   sequence checks and event counts. Before publish, rollback is transaction rollback/restore of
   the disposable copy; after v3 publication, recovery is forward repair with the prior compatible
   application and a newer full-state event run, never surrogate renumbering or consumer DB writes.
7. [x] **Run the full gate and hand back to TAX-07.** Run
   `make -C services/categorization-service test`,
   `make -C services/categorization-service check`, the real-Postgres migration suite,
   affected transaction/analytics projection tests, `make compose-check`, `make notes-check` and
   `git diff --check`. Rebuild/start affected API and workers on disposable stores and inspect
   logs. Fill Outcome with commands, hashes, counts and deviations; resolve the finding and mark
   P2-44 done only after the measured snapshot passes. Then resume P3-21 and the final TAX-07
   read-only dry-run; do not infer approval for bulk writes.

## Risks & rollback

- **Stamping hides an incomplete 008 state.** The bootstrap stamps only inside the same transaction
  after checking every 008 schema object, 13/67 row, 36 merchant, 82 rule and 80 outbox invariant.
  Any mismatch aborts and leaves the database at the original revision and hash.
- **A supposedly free range races with runtime taxonomy creation.** Take database locks before
  reading maxima and hold them through seed insertion/ledger commit. Detect with uniqueness and
  ledger completeness constraints; abort rather than retry with a different mapping for the same
  run ID.
- **Existing integer identity is accidentally changed.** Hash all pre-existing taxonomy rows and
  FK edges and reject any diff. Restore the disposable database and fix the bootstrap; never
  compensate by rewriting transaction or consumer identifiers.
- **Clean and repaired installations diverge in surrogates.** Integer surrogates are deliberately
  environment-local; convergence is defined by pinned UUIDv7/key, hierarchy, lifecycle, rule and
  event semantics. Tests must nevertheless pin each environment's ledger and prove it never
  reallocates after activation.
- **Events escape before validation.** Keep the owner publisher stopped until revision 009 and all
  owner checks pass. If publication has begun, stop publishers/consumers, retain additive owner
  data, repair forward with a new run ID and verify read copies; Alembic downgrade cannot retract
  delivered events.
- **The bootstrap exception is operationally unacceptable.** Do not implement an alternative by
  silently editing 008. Escalate to a separate decision that explicitly chooses migration-history
  replacement or permits amending the unpublished revision, including treatment of databases
  already at 008.

## Outcome (fill in when done)

Completed 2026-08-01. Published migration 008 remains unchanged. The new
`app.tools.tax06_collision_bootstrap` is an explicit revision-007-only bridge: it takes an advisory
and table lock, chooses contiguous ranges above occupied IDs, sequence reservations and 008's
published ranges, installs the same TAX-06 schema/13+67 nodes/36 merchants/82 rules/80 deterministic
outbox snapshots in one transaction, records all UUID/key→surrogate allocations, validates the
complete state and only then stamps 008. Repeating the same run ID returns the recorded allocation;
a different run ID or partial ledger fails closed. Forward revision 009 adopts that ledger or
backfills it for ordinary 008 installations and synchronizes sequences.

The measured live-shaped drill used a logical dump into a disposable PostgreSQL 16 container. The
source was revision 007 with **11 categories** (category 11 `E2E Cat 6b9dea2b`), **41
subcategories**, category/subcategory sequence positions **12/42**, **130 merchants**, **134
rules**, **793 categorization results** and **797 outbox rows**. Bootstrap allocated categories
**24–36** and subcategories **109–175**; revision 009 ended at 24 total categories, 108 total
subcategories, 166 merchants, 216 rules, 793 results, 80 allocation rows and 80 v3 migration events.
The original category, subcategory and result hashes stayed respectively
`d2980217853ec53d4adaae053ff0803b`, `943a988706d4a15c5637efe516b14340` and
`1d30789de89f0d8da44bd3e48614364b`; legacy merchant and rule-reference hashes also matched. The
active source remained revision 007 with its original counts throughout. The disposable container
was removed after verification and is reproducible from a fresh logical dump.

Verification passed: categorization **186 fast tests**, Ruff/format/mypy and **26 real-Postgres
migration tests**; transaction taxonomy projection **11 tests**; analytics Elasticsearch projection
**13 tests**. `make compose-check` passed for 62 services, `make notes-check` and
`git diff --check` passed, the categorization image rebuilt successfully, and the packaged bootstrap
CLI started successfully. Event convergence used the existing isolated consumer/projection suites
rather than publishing the snapshot's pending events into the active RabbitMQ/Elasticsearch stack;
the final 749↔749 live-shaped read-model reconciliation remains P3-21/TAX-07 scope. No bulk
reclassification or environment rollout was authorized or performed.

Operator sequence: stop the owner publisher, capture revision/count/hash/sequence baselines and a
logical backup, restore it to a disposable database, run
`python -m app.tools.tax06_collision_bootstrap --run-id <approved-change-id>`, repeat the same
command to prove idempotency, run `alembic upgrade head`, then verify ledger identity, sequences,
legacy hashes, outbox counts and consumer health before publishers resume. Before publication, an
error rolls back the bootstrap transaction or restores the backup. After publication, retain the
additive owner state and repair forward with a new full-state event run; never renumber existing
surrogates or write consumer databases directly.
