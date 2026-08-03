---
title: TAX-07 — existing-data reclassification dry-run
date: 2026-08-01
status: done
backlog: [TAX-07]
related:
  - plans/2026-08-01-tax01-tax03-taxonomy-foundation.md
  - plans/2026-08-01-tax06-additive-taxonomy-migration.md
  - decisions/2026-08-01-taxonomy-semantics-and-identity.md
---

# TAX-07 — existing-data reclassification dry-run

## Goal

Produce a deterministic, read-only reclassification report for every legacy taxonomy reference
owned by categorization-, transaction- and budget-service. The report must distinguish safe
one-to-one proposals from evidence-dependent splits and protected user decisions, quantify the
before/after analytics effect, and leave all databases and Elasticsearch documents byte-for-byte
unchanged. Its reviewed output is the approval artifact for a later, separately planned bulk
write; generating the report never authorizes that write.

## Context

[TAX-01–03](2026-08-01-tax01-tax03-taxonomy-foundation.md#tax-03-current-to-target-mapping)
approved the complete 10/41 legacy-to-target disposition and explicitly blocked blind remapping
of splits. [TAX-06](2026-08-01-tax06-additive-taxonomy-migration.md#outcome-fill-in-when-done)
activated the 13/67 UUIDv7 taxonomy and versioned read copies without changing transactions,
categorization results, user or learned rules, budgets, planned transactions or analytics
groupings. Those references remain integer-addressed and preserve their original meaning until
this dry-run makes each proposed change and unresolved case reviewable.

The bounded contexts retain ownership of their own data: TAX-07 may call APIs or exchange
versioned artifacts, but no service may inspect or update another service's database. Manual
transaction assignments and user-authored intent outrank automated proposals. Stable UUID/key
identity, not display names, drives every proposal.

## Non-goals

- No update, insert, delete, outbox publication, Elasticsearch reindex/alias swap or bulk write.
- No automatic choice for split mappings, parent-only assignments, own-account ownership,
  MobilePay purpose, person transfers or other evidence-dependent cases.
- No mutation of manual transaction classifications or retargeting of user/learned rules.
- No automatic apportionment or merging of budget amounts.
- No removal of legacy integer IDs, deprecated taxonomy rows or compatibility event versions.
- No sandbox personas (TAX-08), quality gate (TAX-09), ML labels/classifier or AI chat changes.

## Steps

1. [x] **Pin the proposal contract and mapping source.** Add pure-domain TAX-07 dispositions
   beside `services/categorization-service/app/domain/taxonomy_definitions.py`, keyed by the
   legacy IDs and target semantic keys/public UUIDs approved in TAX-03 and pinned by TAX-06.
   Model `safe_one_to_one`, `evidence_proposal`, `manual_review`, `protected` and `unresolved`
   explicitly, with machine-readable reason codes. Add validation tests proving all legacy 10/41
   nodes occur exactly once, every target resolves to the active TAX-06 registry, splits cannot be
   marked safe, and no proposal depends on a display name or list position.
2. [x] **Define a versioned, deterministic report schema.** Add a framework-free report contract
   containing run ID, taxonomy/mapping version, source service and snapshot boundary; aggregate
   counts and amounts; per-disposition/per-source breakdowns; protected-manual counts; unresolved
   reason counts; and stable hashes for optional JSONL detail files. Keep row-level hostile bank
   text and credentials out of logs and the summary; detail output uses internal IDs and the
   minimum normalized evidence required for review. Serializing the same snapshot twice must be
   byte-identical apart from an explicitly supplied run ID.
3. [x] **Build service-owned read-only scanners.** Add dry-run application services and operator
   CLIs in categorization-, transaction- and budget-service. Each scanner reads only its own
   repository through explicit read ports, applies the pinned proposal contract, writes reports
   only to a caller-selected local output directory and runs inside a read-only transaction where
   supported. Cover categorization results plus system/user/learned rules; transactions plus
   planned transactions; legacy budgets plus monthly budget lines. Manual categorization,
   user-authored rules and ambiguous splits must be reported as protected/review rather than safe.
4. [x] **Make evidence-dependent transaction proposals explicit.** Reuse the production
   normalization and constrained-rule semantics through domain/application ports; do not copy the
   rule engine into an operator script. Record which structured evidence justified a candidate,
   whether the proposal changes category type, and why missing/conflicting evidence prevented a
   choice. Add deterministic fixtures for direct remaps and the TAX-03 boundary cases: investment
   versus savings, cash withdrawal, MobilePay direction versus purpose, own-account transfer,
   person transfer, refunds, subscriptions and sports/clothing purchases.
5. [x] **Aggregate without cross-service database access.** Add a repository-level operator
   command under `scripts/` that invokes or consumes the three service-owned report artifacts,
   verifies their schema/mapping versions and snapshot metadata, and emits one summary plus hashed
   detail manifests. It must fail closed for missing services, mixed versions, duplicate source
   shards, invalid hashes or non-terminal/unexplained rows. Record pre/post database table counts,
   taxonomy reference histograms and outbox/inbox maxima so zero mutation is independently
   demonstrable.
6. [x] **Quantify analytics impact without changing analytics.** Derive expected before/after
   group totals from the transaction proposal artifact and compare the before side with the
   current analytics query/read model. Report deltas separately for expense, income, investment,
   cash, savings, own-account and unknown transfers; do not reindex or rewrite Elasticsearch.
   Fail the report when source totals do not reconcile or when an analytics delta lacks a traced
   proposal/reason.
7. [x] **Exercise a production-shaped dry run and create the approval packet.** Against a copied
   or disposable snapshot, run every scanner twice with the same run ID and prove identical
   hashes. Capture total references, safe proposals, protected manual/user choices, review queue,
   unresolved cases, budget collisions and analytics deltas. Include an explicit proposed write
   scope, conflict policy, rollback/forward-repair design and operator checklist, but keep every
   write command absent or disabled. Stop for product/owner approval; any mutation receives a new
   plan and a fresh pre-write snapshot.
8. [x] **Verification and hand-off.** Add deterministic unit tests for proposal semantics and
   report serialization, repository/integration tests proving scanners do not flush writes or
   publish events, and negative controls for malformed/mixed reports and manual-protection
   violations. Run `make -C services/categorization-service test check`,
   `make -C services/transaction-service test check`, `make -C services/budget-service test check`,
   focused analytics reconciliation tests, `make compose-check`, `make notes-check` and
   `git diff --check`. Compare database and Elasticsearch snapshots before/after the live-shaped
   run. Record measured results in Outcome and mark TAX-07 done only when the report is complete;
   do not mark any subsequent write as approved.

## Risks & rollback

- **A dry-run accidentally writes.** Detect with read-only credentials/transactions, SQL write
  guards, outbox/inbox maxima and pre/post table hashes. Abort immediately and discard the copied
  environment; production-shaped execution stays blocked until the offending adapter is removed.
- **The same legacy ID gets different meaning across scanners.** Detect by requiring the same
  mapping version/hash in every shard. Fail aggregation; update the taxonomy owner's mapping and
  rerun all shards rather than patching a report.
- **Automation overrides user intent.** Detect any manual transaction or user/learned rule in the
  safe bucket as a test and runtime invariant failure. Reclassify it as protected/review; never
  infer intent from a global rule.
- **Split mappings manufacture false precision.** Require evidence and a reason code for every
  non-one-to-one proposal. Missing or conflicting evidence becomes unresolved, not a fallback
  target.
- **Budget remaps collide or change totals.** Report target collisions and pre/post totals without
  merging rows. Defer allocation/merge policy to the separately approved write plan.
- **Analytics estimates do not reconcile with source data.** Detect mismatched counts/amounts and
  traced deltas. Keep the source report, mark analytics comparison incomplete and perform no
  reindex or source mutation.
- **Sensitive transaction text leaks into artifacts.** Default to aggregate output and minimized
  normalized evidence in access-controlled detail files; never log raw descriptions. Delete only
  explicitly identified disposable report artifacts through the normal operator cleanup process.

## Outcome (fill in when done)

Completed 2026-08-01. The three service-owned scanners, versioned mapping/report contract and
fail-closed aggregator now cover every measured legacy reference without cross-service database
access. Evidence-dependent transaction rows are evaluated through transaction-service's existing
internal categorization port against the production `ConstrainedRuleEngine`; categorization-service
adds the stable target semantic key to its additive response, so environment-local surrogate IDs
never become migration identity. Requests are deterministically chunked at the production 500-row
limit. Reports retain only direction, target key, tier and confidence—not raw bank descriptions—and
the categorization pipeline no longer logs hostile descriptions on match, fallback or tier failure.

The final production-shaped run used fresh disposable copies: categorization 007 was installed via
the approved P2-44 bootstrap and upgraded to 009, transaction was upgraded 013→014 and budget was
already at 004. An isolated categorization API loaded all **82** constrained rules and **99** total
subcategories. Both complete runs used `run_id=tax07-20260801-final` and the same captured boundary;
every artifact was byte-identical: mapping
`17c7301ed58447d6add056f002ac21ba0a1253920ac98b2b57040b64dd1e0f24`, categorization
`fe46a6494d3616710f36657b3c0bd76a17d03cf666c6e83b479d9b2dceda981c`, transaction
`d45b617345a871bf74bd997e5e068dba8c908a829c6d9b2cad7a625731c8e310`, budget
`fcc41b9e8af690484b8801260c7890bf53767ff3f0e5a627ecc43d6438e42aca` and approval summary
`be8a6daf2618cbb52fc42d71831f1616e93a8fe7548d7610a6c4ad9ec2db791b`.

The aggregate contains **546 safe one-to-one**, **626 evidence proposals**, **527 unresolved**,
**7 manual budget reviews** and **6 protected** references. Transaction-service accounts for all
**749** active transactions: 210 direct proposals, 10 constrained-rule proposals to
`own_accounts_savings`, 527 conflicting-evidence rows and 2 protected manual choices. Analytics
reconciled exactly against P3-21's 749-document live baseline. The traced impact is DKK **630.00**
expense→cash and DKK **6,700.00** income→savings; total signed DKK is unchanged. The approval
section explicitly limits a possible later write to safe/evidence rows, excludes review/protected/
unresolved rows, requires optimistic re-read/skip semantics and a fresh snapshot, and states
`writes_authorized=false`. No write command is present.

All scanner transactions were database-read-only; both runs recorded identical table counts,
reference histograms and outbox/inbox maxima. The active databases remained at categorization 007,
transaction 013 and budget 004, active Postgres remained 749 rows, and Elasticsearch remained 793
documents (749 live plus 44 tombstones). Service tests/checks passed: categorization **187**,
transaction **220 unit + 82 integration**, budget **63 unit + 56 integration**, plus the repository
aggregator tests, image builds/smokes, Compose, notes and diff gates. Disposable databases,
container and report directory were removed after recording hashes. TAX-07 authorizes no bulk
mutation; any reviewed execution requires a separate plan and fresh pre-write evidence.
