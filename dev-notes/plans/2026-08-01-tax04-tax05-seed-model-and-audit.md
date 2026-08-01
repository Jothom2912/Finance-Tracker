---
title: TAX-04–05 — separated seed model and global-rule audit
date: 2026-08-01
status: done
backlog: [TAX-04, TAX-05]
related:
  - ../backlog/TAXONOMY-OPTIMIZATION.md
  - 2026-08-01-tax01-tax03-taxonomy-foundation.md
  - ../decisions/2026-08-01-taxonomy-semantics-and-identity.md
  - ../decisions/2026-08-01-seed-evidence-and-rule-confidence.md
  - ../architecture/services/categorization-and-ai-services.md
  - ../patterns/categorization-pipeline.md
---

# TAX-04–05 — separated seed model and global-rule audit

## Goal

Produce a migration-ready, domain-owned seed specification in which taxonomy definitions,
canonical merchants and aliases, and constrained categorization rules are separate concepts.
Audit every one of the 130 legacy global mappings against the approved 13/67 taxonomy and record
one explicit disposition per mapping. Completion means the target manifests validate
deterministically, every retained rule has a stable target key, match field, direction constraint,
confidence and provenance, and no database, historical migration or user data has changed.

## Context

TAX-01–03 approved the semantics, stable keys and complete legacy-node mapping in the
[foundation plan](2026-08-01-tax01-tax03-taxonomy-foundation.md). Current code still combines a
text fragment, merchant display label and subcategory assignment in
`services/categorization-service/app/domain/taxonomy.py`; migrations 004 and 005 import that live
dictionary into both `merchants` and `categorization_rules`. At runtime the provider reduces all
global rules to unconstrained description `contains` matches, while sign-specific behavior is a
hard-coded adapter override.

TAX-04 must define the separated contract before TAX-05 judges individual mappings. TAX-06 owns
schema changes, UUID generation, additive persistence and event repair, so this phase creates an
executable target specification and audit evidence without silently changing fresh installs or
running systems.

## Non-goals

- No Alembic revision, schema/model/repository change or edit to migrations 001–007.
- No replacement, deletion or insertion of current database merchants or global rules.
- No taxonomy seed activation, UUID allocation, event emission or downstream read-copy update.
- No recategorization of transactions, learned/user-rule rewrite, budget remap or analytics repair.
- No ML/LLM classifier, per-user merchant memory, provider parser or sandbox-persona fixture.
- Preserve the current rule priority ladder (learned 10, user 50, global 100), user-rule APIs and
  longest-match behavior until a separately approved migration changes them.

## Steps

1. [x] **Freeze inputs and define the audit vocabulary.** Extend the deterministic baseline guard
   under `services/categorization-service/tests/unit/test_taxonomy_baseline.py` (or a focused
   sibling audit test) to expose a stable sorted snapshot of all 130 legacy entries. Define the
   allowed audit dispositions (`retain`, `constrain`, `replace`, `persona_only`, `remove`) and
   require legacy keyword, old target, proposed target key, rationale and replacement linkage.
   Negative controls must fail for a missing legacy row, duplicate disposition or unknown target
   key; they must not weaken the existing 10/41/130 baseline assertions.
2. [x] **Design TAX-04's pure-domain seed contracts.** Add typed, framework-free value objects in
   `services/categorization-service/app/domain/` for (a) taxonomy definitions keyed by the approved
   semantic keys, (b) canonical merchants with zero or more provider/country-scoped aliases, and
   (c) categorization rules that reference a merchant/alias or an explicit pattern. Rules must
   express match field, operator, transaction direction, optional provider/country and amount
   bounds, confidence, provenance/source reference, seed version and lifecycle state. Specify
   invariants for normalization, alias uniqueness, inclusive amount bounds and typed fallback
   targets. Keep UUIDs absent until TAX-06 pins UUIDv7 values.
3. [x] **Architecture review checkpoint — stop for approval.** Review whether aliases are
   identity evidence rather than category owners, whether free-text rules may ever be high
   confidence, and how direction is derived consistently from the transaction amount. Record any
   non-obvious accepted trade-off with `dev-notes-decision`. Do not audit rules against an
   unsettled contract.
4. [x] **Materialize separate target manifests without activating them.** Split the approved
   13/67 definitions, merchant identities/aliases and constrained global rules into clearly named
   modules under `services/categorization-service/app/domain/` (for example
   `taxonomy_definitions.py`, `merchant_aliases.py` and `seed_rules.py`). Leave
   `DEFAULT_TAXONOMY`, `SEED_MERCHANT_MAPPINGS`, migrations 004/005 and the runtime provider on the
   legacy path through TAX-06. Add import/validation tests proving the target manifests contain no
   mutable-name references, orphan targets, duplicate aliases or rules lacking provenance.
5. [x] **Complete TAX-05's 130-row audit.** Give every current mapping exactly one disposition and
   preserve the audit as executable data beside the target manifests, with a human-readable
   generated summary in this plan or its Outcome. Explicitly review broad fragments (`bar`,
   `cafe`, `power`, `normal`, `su`, `rente`), payment-channel terms, personal names and local
   one-offs. Retain only rules whose bank text supplies enough evidence; constrain ambiguous
   direction/provider/field cases, move persona evidence to TAX-08 candidates, and remove unsafe
   global guesses. Add safe Danish aliases only with named provenance and a collision review.
6. [x] **Prove semantics, coverage and migration readiness.** Add table-driven domain tests for
   merchant-field versus free-text matching, positive/negative/zero direction, Danish
   normalization, provider/country constraints, amount-bound edges, precedence and fallback. Run
   the target rules against curated positive cases plus adversarial near-matches; assert that
   rejected broad/personal entries do not match. Produce counts by disposition, target and
   confidence, plus the exact retained/replaced rule total that TAX-06 must migrate.
7. [x] **Verify and hand off.** Run `make -C services/categorization-service test`,
   `make -C services/categorization-service check`, `make notes-check` and `git diff --check`.
   Confirm with a migration-upgrade test or equivalent snapshot that a database upgraded only
   through revision 007 still receives the unchanged 10/41/130 legacy seed. Update the TAX-04/05
   roadmap rows and this plan's Outcome with measured audit totals and rejected candidates, then
   hand the approved manifests to a separate TAX-06 plan; do not create or execute its migration.

## Risks & rollback

- **Historical seed drift:** moving the legacy constants can alter clean-database upgrades even
  without a new revision. Detect by the revision-007 snapshot and existing baseline; rollback the
  target-manifest wiring while leaving the legacy constants/migrations untouched.
- **False precision:** a merchant alias or short fragment can still identify several purposes.
  Detect with collision/adversarial fixtures and disposition summaries; downgrade confidence,
  constrain it or remove it rather than widening coverage.
- **Direction ambiguity:** amount signs may differ at an adapter boundary. Pin the current
  positive/negative convention in contract tests before encoding constraints; if evidence
  conflicts, leave the rule inactive for TAX-06 rather than guessing.
- **Audit incompleteness:** dictionary edits can make a prose checklist stale. Derive exact
  legacy coverage from executable audit rows and fail on missing, duplicate or extra legacy keys.
- **Premature behavior change:** target modules could accidentally be imported by runtime startup.
  Keep activation out of provider/repository wiring and prove unchanged legacy migration/runtime
  fixtures. All changes in this phase are code/note reversions; no data rollback is required.

## Outcome (fill in when done)

TAX-04 now has pure-domain contracts plus separate inactive manifests for all 13 parent and 67
child taxonomy definitions, 36 canonical merchants and their aliases, and 82 constrained target
rules. The accepted contract keeps aliases category-neutral, caps description matching at medium
confidence, derives incoming/outgoing from the amount sign, treats zero as directionless, and
requires one evidence source plus provenance per rule. The legacy runtime provider, models and
migrations remain untouched.

TAX-05 gives all 130 legacy mappings exactly one executable disposition: **47 retain, 32
constrain, 3 replace, 24 persona-only and 24 remove**. The resulting 82 rules comprise 42 merchant
rules and 40 explicit-pattern rules, with 40 high- and 42 medium-confidence outcomes; 75 are
outgoing and 7 incoming. No low-confidence global rule is activated. Broad merchants `normal`
and `power` survive only as structured, medium-confidence evidence targeting
`shopping_unspecified`; broad fragments such as `bar`, `cafe`, `su` and `rente`, personal names
and undocumented local merchants do not enter the target rules. The three replacements normalize
McDonald's, `pizzeria` and `kiosk` evidence.

Verification passed with 181 fast service tests, 21 real-Postgres migration tests, Ruff lint and
format checks, full-service mypy, `make notes-check` and `git diff --check`. The migration suite
now pins exactly 130 legacy merchant rows and 130 legacy rule rows through revision 007, proving
that this phase did not change clean-install behavior. TAX-06 can consume the inactive manifests
in an additive migration; it must not infer UUIDs or rewrite historical migrations.
