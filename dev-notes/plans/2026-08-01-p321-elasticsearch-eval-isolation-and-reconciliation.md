---
title: P3-21 — isolate eval documents and reconcile the transaction read model
date: 2026-08-01
status: done
backlog: [P3-21]
related:
  - ../findings/2026-07-26-eval-seed-writes-to-prod-index.md
  - 2026-07-26-p320-cleanup-script-outbox.md
  - 2026-08-01-tax07-existing-data-reclassification-dry-run.md
---

# P3-21 — isolate eval documents and reconcile the transaction read model

## Goal

Structurally isolate AI retrieval-eval fixtures from the live transaction alias, remove the known
66 synthetic documents from a disposable snapshot copy, explain or repair the remaining category-1
count discrepancy, and produce a fail-closed Postgres↔Elasticsearch reconciliation over IDs,
counts and signed DKK amounts. Completion means the measured snapshot copy contains exactly 749
live Postgres transactions and 749 corresponding live Elasticsearch documents with no missing or
extra IDs and matching global/per-user/per-account/per-category counts and amounts.

## Context

[P3-21](../findings/2026-07-26-eval-seed-writes-to-prod-index.md) records that
`services/ai-service/tests/eval/es_seed.py` writes 66 user-9001/9002 fixtures through the live
`transactions` alias. TAX-07's disposable source has 749 Postgres rows while the current alias has
816 live documents. Removing the 66 known fixtures leaves one unexplained document; category 1 has
the extra count even though its signed DKK amount already matches. TAX-07 correctly refuses an
approval summary until this difference is zero.

## Non-goals

- No transaction reclassification, taxonomy-reference rewrite, bulk production mutation or TAX-07
  approval packet. This plan repairs test isolation and read-model hygiene only.
- No deletion by guessed category/user/count. Every removal must be tied to an explicit ID-set
  difference and provenance.
- No direct change to Postgres truth and no cross-service database write. Elasticsearch is a
  reconstructible read model; source rows and outbox/inbox state remain unchanged.
- No removal of historical physical indices merely because they are unaliased; route any such
  cleanup separately unless it is required for an unambiguous reconciliation.

## Steps

1. [x] **Pin the baseline and the unexplained row.** On fresh disposable Postgres and Elasticsearch
   copies, resolve the exact physical index behind `transactions`, capture alias/index mappings and
   immutable snapshots of live document IDs, source transaction IDs, deleted flags, user/account/
   category histograms and signed/absolute amount totals. Classify all 67 extra IDs: prove 66 match
   the eval offset/users/fixture manifest and identify the final document's full projection/source/
   event provenance. Abort if the measured sets differ from the recorded 749↔816 shape.
2. [x] **Give evals a structurally isolated index.** Change
   `services/ai-service/tests/eval/es_seed.py` and its eval helpers/tests to use a dedicated,
   configurable `transactions_eval` alias backed by a strict mapping equivalent to the production
   transaction mapping. Seeding and cleanup may target only that alias; reject `transactions` and
   `transactions_v2` as eval targets. Point embedding backfill/retrieval evaluation explicitly at
   the eval alias/prefix rather than altering analytics' production settings. Add positive tests
   for repeatable 66-document seeding and negative tests proving the live alias is never called.
3. [x] **Repair the disposable live read model from source truth.** Delete the 66 proven fixture
   IDs from the disposable live index. For the remaining extra category-1 document, use its actual
   cause: remove it only if it has no source row/tombstone event, or replay/reproject the canonical
   source event if the discrepancy is a stale/mis-shaped projection. Record the exact ID, cause and
   repair. Never delete a source-backed row to make counts fit.
4. [x] **Add a reusable fail-closed reconciler.** Add a read-only tool under analytics tooling or
   repository scripts that compares Postgres source rows with non-deleted ES documents by
   transaction ID and reports missing/extra IDs plus exact `Decimal` counts and signed/absolute
   amounts globally and grouped by user, account, category and month. It must reject duplicate ES
   transaction IDs, alias fan-out, schema/mapping mismatch, parse loss and partial pagination.
   Machine-readable output must hash sorted inputs/results for TAX-07 evidence.
5. [x] **Prove 749↔749 and non-mutation.** Run reconciliation twice against the same disposable
   copies and require identical hashes, empty ID differences, 749/749 counts and exact DKK totals in
   every grouping. Compare Postgres tables/outbox/inbox and the non-transaction ES aliases before
   and after; only the explicitly classified transaction documents may differ. Run the AI eval
   twice and prove its 66 documents exist only in the eval alias while the live 749 hash is stable.
6. [x] **Verification and hand-off.** Run affected AI and analytics tests/checks, focused real-ES
   integration/eval tests, `make compose-check`, `make notes-check` and `git diff --check`; rebuild
   and smoke-test affected images. Record IDs, counts, amounts, hashes, mapping versions and repair
   commands in Outcome, resolve P3-21, then resume TAX-07's final three-scanner dry-run. Any active
   Elasticsearch cleanup still requires an explicit operator target/backup confirmation after the
   disposable proof.

## Risks & rollback

- **Fixture deletion removes real data.** Require the intersection of explicit fixture IDs,
  eval-user ownership and absent Postgres IDs; compare the full document body to the fixture
  manifest. Restore the disposable ES snapshot/reindex if any predicate fails.
- **The extra row is source-backed but stale.** Determine event/source provenance before action.
  Replay or rebuild the projection rather than deleting truth-backed state; verify timestamp guards
  and tombstones.
- **Eval behavior diverges under a separate mapping.** Generate/reuse the same strict transaction
  mapping contract and add a drift assertion. Eval-specific vectors may extend it but cannot weaken
  production-required fields.
- **Count equality hides money drift.** Reconciliation is ID- and exact-Decimal-based and groups by
  every relevant dimension; 749↔749 alone is insufficient.
- **Cleanup mutates the active alias prematurely.** All implementation drills use disposable
  copies. An active cleanup needs a named alias/physical index, snapshot, exact delete manifest and
  post-delete reconciliation; otherwise stop.

## Outcome (fill in when done)

Completed 2026-08-01. AI retrieval fixtures now seed only the guarded `eval_transactions` alias;
both `transactions` and `transactions_v2` are rejected. An opt-in `docker-compose.eval.yml` starts
an analytics API with `ES_INDEX_PREFIX=eval_`, so retrieval queries, mapping bootstrap, embedding
backfill and fixture writes are structurally isolated without adding an eval process to the
production/Kubernetes topology. Two seed runs each converged on exactly 66 eval documents while the
live index count remained unchanged. All 66 received bge-m3 embeddings, and the isolated retrieval
golden/tenant tests passed **2/2**.

The unexplained category-1 row was Elasticsearch `_id=99999999`: a categorization-only partial
document with no `user_id`, `account_id`, `amount` or `tx_date`, hence one extra category count but
no amount contribution. It had no transaction source row, transaction outbox event,
categorization result or categorization outbox event. Its body showed transaction/category 1,
subcategory 1 and rule/high metadata; it was a stranded update-before-create projection, not
financial truth.

The manifest cleanup requires exactly one alias target, validates all 66 fixture IDs/users/bodies
plus the complete classified orphan body, and refuses live aliases unless the operator supplies an
explicit allow flag and expected physical index. A disposable reindex was cleaned first. The
reconciler then produced **749 Postgres ↔ 749 ES**, no missing/extra IDs, no field mismatch and no
global/user/account/category/month count or signed-DKK mismatch. After explicit operator approval,
the same 67-item manifest was removed from `transactions` only after confirming it still resolved
solely to `transactions_v2`. Two active reconciliations were byte-identical:
`postgres_hash = elasticsearch_hash = 505a9ae23432ee3f3cdec7256ffb507fb084fc394e4f47a36f44c81d40177821`
and `report_hash = d95e21157a3328acb3dac125370a1d1750d76cd18a908a35b26dcdba314152e9`.
The live physical index now holds 793 total documents: 749 live projections plus 44 legitimate
tombstones. The eval alias holds 66 fixtures. The disposable P3-21 index was removed after proof.

The reusable read-only transaction maintenance CLI uses a point-in-time ES snapshot, exact total
hits, stable pagination, duplicate detection, strict required-field parsing and Decimal-cent
comparison. Verification passed: AI **93 non-live tests** plus **2 isolated retrieval evals**;
transaction **211 unit + 82 integration tests**; Ruff, formatting and mypy for both services;
transaction image build/CLI smoke; main Compose parity and the eval override config; notes and diff
gates. The Postgres write model/outbox/inbox were read-only throughout. TAX-07 can now use the
749↔749 baseline; no reclassification write was authorized or performed.
