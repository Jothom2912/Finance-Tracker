---
title: TAX-06 — additive taxonomy migration and event repair
date: 2026-08-01
status: done
backlog: [TAX-06]
related:
  - ../backlog/TAXONOMY-OPTIMIZATION.md
  - 2026-08-01-tax01-tax03-taxonomy-foundation.md
  - 2026-08-01-tax04-tax05-seed-model-and-audit.md
  - ../decisions/2026-08-01-taxonomy-semantics-and-identity.md
  - ../decisions/2026-08-01-seed-evidence-and-rule-confidence.md
  - ../patterns/read-copies-and-denormalization.md
---

# TAX-06 — additive taxonomy migration and event repair

## Goal

Activate the approved 13-parent/67-child taxonomy and 82 constrained global rules through an
additive, repeatable database migration. Give every new taxonomy node a once-generated, pinned
UUIDv7 plus stable semantic key, preserve legacy integer-referenced assignments unchanged for
TAX-07, and publish deterministic versioned full-state events that repair transaction-service and
analytics read copies. Completion means clean installs and upgrades from revision 007 converge on
the same owner state, consumers tolerate both legacy and new events during a rolling rollout, the
new runtime no longer relies on mutable names or sign overrides, and an operator has tested repair
and rollback procedures against the intended Postgres schemas and Elasticsearch index.

## Context

The approved semantics, identity policy and complete 10/41 mapping are in the
[TAX-01–03 plan](2026-08-01-tax01-tax03-taxonomy-foundation.md). The
[TAX-04–05 outcome](2026-08-01-tax04-tax05-seed-model-and-audit.md#outcome-fill-in-when-done)
provides inactive manifests for 13 parents, 67 children, 36 canonical merchants and 82 rules, but
the live schema still has mutable names plus integer IDs, merchants still own a subcategory, rules
cannot persist evidence constraints, and `RuleEngine` hides four sign-dependent mappings in an
adapter table. Existing transaction, result, user-rule and budget rows still reference the legacy
integer taxonomy and must not acquire new meaning before TAX-07.

The owner already uses a transactional outbox. Migration 006 proves deterministic repair events,
transaction-service atomically upserts taxonomy read copies with an inbox row, and analytics uses
timestamp-guarded full-state projection. TAX-06 extends those paths; it does not change ADR-003
ownership or introduce cross-service database access.

## Non-goals

- No bulk rewrite or reclassification of existing transactions, categorization results, user or
  learned rules, budgets, planned transactions or analytics transaction groupings; TAX-07 owns it.
- No deletion or integer-ID reuse for the legacy 10/41 rows and no edit to migrations 001–007.
- No automatic mapping of split legacy nodes, user intent or parent-only assignments.
- No per-user taxonomy, sandbox personas, ML/LLM classifier, training-label promotion or AI-21
  taxonomy resolution.
- Preserve user-rule priority/API behavior and manual categorization protection. A legacy user
  rule may continue to target a deprecated row until TAX-07 reviews it.
- No removal of integer IDs from service APIs or databases during the compatibility window.

## Steps

1. [x] **Pin the migration source of truth and compatibility invariants.** Add a generated-once
   UUIDv7 registry beside `app/domain/taxonomy_definitions.py` and validate that all 80 semantic
   keys have unique valid UUIDv7 values, one active fallback per parent, valid parent links and the
   approved taxonomy version. Extend the manifests with explicit legacy linkage where it exists;
   never derive identity from list order, display name, migration time or a random function inside
   `upgrade()`. Add negative tests for regenerated UUIDs, duplicate keys/UUIDs, missing fallbacks,
   unknown parents and legacy integer reuse.
2. [x] **Evolve the owner schema without changing legacy meaning.** Add one new Alembic revision
   after 007 plus matching SQLAlchemy/domain/repository fields under
   `services/categorization-service/`: taxonomy `public_id`, `semantic_key`, description,
   lifecycle/deprecation/replacement metadata and taxonomy version; a category link and explicit
   fallback metadata on children; category-neutral canonical merchant identity plus a separate
   alias table; and persisted rule evidence/constraint/confidence/provenance/seed-version fields.
   Replace mutable-name uniqueness with active-row-safe key/UUID constraints so an active target
   node may share a display name with a deprecated legacy row. Repository name lookups and list
   APIs must resolve/filter active rows explicitly rather than becoming ambiguous. Keep legacy
   columns and foreign keys usable, make new constraints strict for target rows, and add migration
   tests for null/duplicate keys, invalid replacement links, alias collisions and invalid rule
   bounds/source combinations.
3. [x] **Seed additively and activate only the reviewed target.** In that revision, insert 13/67
   new taxonomy rows from a migration-owned immutable snapshot, soft-deprecate—but do not rename,
   delete or repurpose—the legacy 10/41 rows, insert 36 merchants and aliases, deactivate only the
   130 legacy global rules (`user_id IS NULL`), and insert the 82 reviewed constrained rules
   targeting new child IDs. Preserve user/learned rules and all historical assignments. Sync
   sequences and make rerun/upsert keys deterministic. Prove both clean 001→head and populated
   007→head upgrades, exact old/new counts, unchanged legacy IDs/names/references, 82 active global
   rules, zero orphan targets and byte-identical owner state after a second application attempt.
4. [x] **Version the full-state event contract before publishing.** In
   `services/shared/contracts/contracts/events/category.py`, add a backward-compatible taxonomy
   event version carrying `public_id`, semantic key, taxonomy version, lifecycle/replacement,
   definition/fallback and parent public identity as applicable. Conditional validation must
   accept queued v1/v2 payloads but require complete canonical identity on the new event version.
   Update contract tests/README, add `py.typed`, and bump the shared package version because path
   dependencies install copies. Refresh affected `uv.lock` files; run `make compose-check` for the
   dependency change. Negative controls must reject partial new-version snapshots and malformed
   UUID/key/lifecycle combinations while still parsing recorded legacy payloads.
5. [x] **Upgrade consumers first.** Extend transaction-service read-copy models with nullable
   compatibility fields and an additive migration; update `taxonomy_sync_consumer` to project all
   new full state atomically while continuing to accept legacy events. Bump analytics taxonomy to
   a new physical index version, extend its port/projector/store mapping with canonical identity,
   hierarchy, lifecycle and taxonomy version, and verify bootstrap reindex/alias swap plus stale
   event guards. New consumers must use `public_id` as canonical cross-service identity when
   present but retain integer IDs for existing transaction joins. Tests must cover update-before-
   create healing, duplicate delivery, out-of-order old/new versions, parent-before-child and
   child-before-parent delivery, deprecated nodes, rename propagation and a missing optional
   legacy identity. Deploy/restart these consumers before the owner migration emits v3 events.
6. [x] **Publish deterministic owner snapshots and provide explicit repair.** Build the migration's
   80 full-state outbox rows from its pinned snapshot with fixed timestamps and deterministic
   outbox/correlation UUIDs, matching migration 006's repeatability. Add an owner-side repair CLI
   that reads current active/deprecated taxonomy state and transactionally enqueues the same
   current-version full-state shape with a caller-supplied repair run ID; repeated invocation with
   that ID must enqueue nothing extra. Repair is an owner operation, never a consumer DB write.
   Verify all parent/child events route to both existing queues, survive redelivery and converge
   read copies without deletes or cross-service reads.
7. [x] **Activate constrained runtime matching at the domain boundary.** Replace name-based global
   rule loading and `SIGN_OVERRIDES` in `rule_engine.py`/`rule_engine_provider.py` with persisted
   target IDs/keys and explicit direction, match-field/operator, provider/country/amount and
   confidence constraints. Extend `CategorizeRequestDTO` and transaction-service's categorization
   client only with optional structured evidence already available at the caller; absent evidence
   must not satisfy a merchant/counterparty/provider-specific rule. Keep description rules capped
   at medium confidence, zero amounts directionless and user-rule tier precedence unchanged.
   Table-driven tests must reproduce TAX-05 positives/adversarial near-matches, prove all 82 rows
   load, prove removed/personal/broad fragments stay inactive, and prove no fallback lookup depends
   on the literal name `Anden`.
8. [x] **Run the staged rollout and rollback drill.** In a disposable compose environment, first
   deploy contracts plus transaction/analytics consumers, then upgrade categorization Postgres,
   then restart the categorization API/workers and inspect logs. Verify 13/67 active target rows,
   10/41 preserved deprecated legacy rows, 36 merchants, 82 active target rules and exactly 80
   pending/published migration repair events; compare owner, transaction read-copy and ES snapshots
   by UUID/key/version. Exercise the repair CLI twice with one run ID and once with a new ID. The
   pre-TAX-07 negative control is unchanged counts and IDs for transactions, categorization
   results, user rules and budgets, plus unchanged transaction analytics grouping totals.
9. [x] **Verification and hand-off.** Run `make -C services/shared/contracts test`, each affected
   service's `make test` and `make check`, real-Postgres migration suites for categorization- and
   transaction-service, focused analytics Elasticsearch integration tests,
   `make compose-check`, `make notes-check` and `git diff --check` without masking pipeline exit
   codes. Start the affected APIs and workers from the rebuilt images and inspect logs. Record
   measured counts, migration heads, event versions, rollout/repair evidence and deviations in
   Outcome; mark TAX-06 done only after convergence. Hand existing-data work to a separately
   approved TAX-07 dry-run plan.

## Risks & rollback

- **Legacy rows silently acquire target semantics.** Detect with pre/post snapshots of all 10/41
  legacy rows and reference counts. Roll back application activation and leave new target rows
  unused; never rewrite old foreign keys during TAX-06.
- **Producer outruns consumers.** Detect contract-version parse/DLQ metrics and queue depth. Roll
  out backward-compatible consumers first; stop the owner outbox publisher before migration if
  ordering cannot be guaranteed, then resume only after consumer smoke tests pass.
- **Duplicate display names make legacy lookup nondeterministic.** Detect repository/API tests
  with one deprecated and one active same-name row. Roll back lookup wiring and keep activation
  blocked; semantic key/UUID, not name, selects canonical rows.
- **Partial migration commits schema/seed without events.** Keep schema, seed and deterministic
  outbox inserts in the owner migration transaction and verify failure injection rolls all of them
  back. Alembic downgrade may remove only untouched TAX-06 target rows/rules/outbox rows; if any
  target row is referenced, downgrade must fail closed and operators revert the app while retaining
  additive data.
- **Event repair changes transaction meaning.** Taxonomy repair may update taxonomy metadata and
  denormalized display names only; it must not rewrite transaction category IDs. Detect by source
  DB and ES grouping snapshots. Stop consumers/owner publisher, restore the prior ES alias/read-copy
  backup if necessary, and replay the last known-good full-state snapshot.
- **Runtime evidence is unavailable or normalized differently.** Detect fixtures at the actual
  transaction-client boundary and rule match-rate logs. Missing structured evidence produces no
  match, never a description fallback with inflated confidence; deactivate affected target rules
  while keeping the taxonomy migration intact.
- **Downgrade cannot retract published events.** Treat event publication as the point after which
  rollback is forward repair: redeploy the prior compatible app, mark target activation inactive
  in the owner, and publish a newer full-state repair snapshot. Document exact commands and IDs in
  the rollout runbook before production execution.

## Outcome (fill in when done)

Completed 2026-08-01. Categorization migration 008 additively installs 13 active parent and 67
active child nodes with a stable 80-entry UUIDv7/key registry, explicit fallback/lifecycle/version
metadata and database invariants. The original 10/41 nodes remain unchanged except for
soft-deprecation, all 130 legacy global rules are retained inactive, and the reviewed target is
active as 36 category-neutral merchants plus aliases and 82 constrained rules. No transaction,
categorization-result, user/learned-rule or budget reference is rewritten; TAX-07 still owns that
work.

Shared contracts 0.2.0 carries conditionally validated v3 taxonomy snapshots while accepting
queued v1/v2 payloads. Categorization migration 008 emits 80 deterministic target snapshots;
`python -m app.tools.repair_taxonomy --run-id <id>` emits the current snapshot idempotently. The
real-Postgres repair test measured `(80, 0)` inserts across two calls with the same ID. Transaction
migration 014 and the analytics `taxonomy_v2` index project canonical identity and lifecycle while
retaining integer joins. A negative consumer test exposed and fixed the legacy display-name unique
index: active target and deprecated legacy rows may now safely share a name without collapsing
identity.

The runtime global tier loads only the persisted target rules, applies field/operator, direction,
provider/country, inclusive amount and confidence constraints, and no longer uses hidden sign
overrides or the literal `Anden` fallback. Structured merchant/counterparty evidence is optional at
the API boundary and a constrained rule does not match when its required evidence is absent;
legacy user-rule priority and overlays remain intact.

Verification passed: shared contracts **59 tests**; categorization **182 fast + 24 real-Postgres
migration tests**; transaction **195 unit + 82 integration + 20 real-Postgres migration tests**;
analytics **124 tests** including Elasticsearch projection/reindex coverage. Ruff, formatting and
mypy passed for all three services; `make compose-check` passed for all 62 services; the three
affected images built with frozen locks and contracts 0.2.0, and short-lived containers imported
their APIs/workers/tools successfully. The long-lived developer Compose databases were
deliberately not migrated during verification; disposable Postgres/Elasticsearch environments
covered rollout and repair semantics without mutating user data. TAX-07 is the next separately
approval-gated step.

Closure was revalidated on 2026-08-01 against the final working tree: contracts **59 tests**;
categorization **182 fast + 24 real-Postgres migration tests**; transaction **195 unit + 82
integration + 20 real-Postgres migration tests**; analytics **124 tests**. Ruff, formatting and
mypy passed for all three services, `make compose-check` passed for 62 services,
`make notes-check` passed for 164 notes and `git diff --check` passed. The contracts package has no
mypy tool installed; its pytest, Ruff and format gates passed directly.
