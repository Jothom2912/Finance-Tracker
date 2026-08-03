---
title: TAX-13 — honest unknown fallback instead of shopping_unspecified
date: 2026-08-03
status: open
backlog: [TAX-13]
related:
  - ../findings/2026-08-03-taxonomy-activation-breaks-live-categorization.md
  - ../decisions/2026-08-01-taxonomy-semantics-and-identity.md
  - ../decisions/2026-08-01-seed-evidence-and-rule-confidence.md
  - 2026-08-01-tax06-additive-taxonomy-migration.md
  - ../backlog/TAXONOMY-OPTIMIZATION.md
---

# TAX-13 — honest unknown fallback instead of shopping_unspecified

## Goal

An uncategorized transaction must read as unknown, not as a real spending category. Today the
absolute fallback is hardcoded to `shopping_unspecified`, so every unmatched row is filed under
Shopping and inflates that category in budgets and analytics. Done means: typed review buckets exist
as additive taxonomy nodes, the fallback resolves to the one matching the transaction's direction,
the 13 rows already mislabelled by this defect are repaired through the normal service-owned path,
and a test fails if the absolute fallback is ever a purpose-bearing category again.

## Context

[The reachability finding](../findings/2026-08-03-taxonomy-activation-breaks-live-categorization.md)
measured that only 7 of 82 active rules can fire from the import path, and that everything else lands
on `shopping_unspecified` at `rule_engine_provider.py:219`. Cause 3 in that finding is this plan.

The taxonomy already has 11 parent-level `*_unspecified` fallbacks plus `unknown_transfer` and
`other_income`, but **no unknown-purchase bucket at all** — which is why activation had to point the
absolute fallback at a real category. The roadmap asked for typed review buckets (`Ukendt køb`,
`Ukendt indbetaling`, `Ukendt overførsel`) precisely so model quality stays visible; only the third
was ever created.

**TAX-14 is a hard prerequisite, not a nice-to-have.** Direction is currently inferred from the sign
of an amount that transaction-service never signs, so every row presents as incoming. If this plan
shipped first, a direction-aware fallback would label all unknown spending `Ukendt indbetaling` —
trading one wrong label for another. TAX-13 branches on direction, so direction must be trustworthy
before it means anything.

## Non-goals

- No change to the 7 reachable rules, the 42 merchant-field rules or the direction contract; those
  are TAX-12 and TAX-14.
- No change to the pinned TAX-07 mapping registry. `shopping_unspecified` appears in
  `app/domain/reclassification.py` as frozen evidence; its hash
  `17c7301ed58447d6add056f002ac21ba0a1253920ac98b2b57040b64dd1e0f24` must stay byte-identical.
- No re-categorization of anything except rows whose tier is `fallback`. Manual, user, gold and
  rule-tier assignments stay untouched, as do the 527 unresolved and 6 protected TAX-10 exclusions.
- No removal or renaming of `shopping_unspecified`; it remains the legitimate parent-level fallback
  for Shopping. Only its role as *absolute* fallback goes away.
- No new per-user custom categories (F2-15) and no classifier work.

## Steps

1. [ ] **Decide and record the bucket shape.** Two new nodes: `unknown_purchase` ("Ukendt køb",
   expense) and `unknown_income` ("Ukendt indbetaling", income); `unknown_transfer` is reused as is.
   `unknown_purchase` needs an expense parent and none of the 11 existing purposes can host it
   without hiding unknown inside a purpose, so add parent `unknown_spending` ("Ukendt", expense) —
   taking the taxonomy to 14/69. Record this in a decision note with the rejected alternative
   (hanging it under an existing parent) and the reason: a fallback under `Shopping` or
   `financial_costs` is what caused this finding. Mark all three nodes `is_fallback` and exclude them
   from rule targets.
2. [ ] **Additive migration.** New revision in `services/categorization-service/migrations/versions/`
   following 008/009 as the reference: insert the parent and two subcategories with fresh UUIDv7
   `public_id`, stable `semantic_key`, next `taxonomy_version`, and emit the same deterministic
   full-state taxonomy events so transaction- and analytics-service read copies heal themselves.
   Extend `taxonomy_definitions.py` and `_FALLBACK_KEYS`, and allocate surrogates through the
   `taxonomy_surrogate_allocations` ledger rather than fixed IDs — the P2-44 lesson.
   Never edit a published migration.
3. [ ] **Replace the hardcoded absolute fallback.** In `rule_engine_provider.py`, drop the
   `shopping_unspecified` lookup and expose a resolver keyed by direction, returning
   `unknown_purchase` / `unknown_income` / `unknown_transfer`. `CategorizationService._absolute_fallback`
   takes the direction the pipeline already has, keeps tier `fallback`, confidence `low` and
   `needs_review=true`. No silent default: if the direction is not one of the three, fail loudly
   rather than pick a category — an unlabelled error is recoverable, a wrong label is not.
4. [ ] **Repair the mislabelled rows.** Re-categorize only the rows at tier `fallback` pointing at
   `29/139` — 13 transactions plus their categorization results — through the service's own write
   path so the normal `transaction.updated` events carry the change into Elasticsearch. Reuse the
   TAX-10 writer shape; do not hand-patch Elasticsearch and do not touch protected tiers.
5. [ ] **Verification.** Unit tests: fallback per direction; a **guard test that the absolute
   fallback's semantic key is in `_FALLBACK_KEYS` and is not a purpose-bearing node**, which is the
   test whose absence let this ship; the loud failure on an unknown direction. Migration test:
   14/69 nodes, ledger completeness, and that legacy rows and the 82 rules are untouched. Then
   categorize the seven real descriptions from the finding through the running service and assert no
   result is `shopping_unspecified`. Run `make -C services/categorization-service test check`,
   `make -C services/categorization-service test-migrations`,
   `make -C services/transaction-service test check`, focused analytics projection tests,
   `make compose-check`, `make notes-check` and `git diff --check`. Finally reconcile
   Postgres↔Elasticsearch and confirm the repaired rows read as `Ukendt køb` in the UI.

## Risks & rollback

- **Fallback flips to the wrong type because direction is still unsigned.** This is the TAX-14
  dependency. Detect before merging by categorizing a known outgoing description and asserting the
  fallback is `unknown_purchase`; if it returns `unknown_income`, TAX-14 has not landed and this plan
  must not ship.
- **Analytics reclassifies unknown spend as a new category and totals move.** `unknown_spending` is
  expense-typed, so consumption totals should be unchanged while Shopping drops. Verify per-category
  before/after counts and signed DKK, and require the total to be identical.
- **Read copies keep the old parent set.** Prove the full-state events drained and that
  transaction/analytics copies hold 14/69 keyed nodes before declaring done; repair forward with a
  new full-state run, never by writing a consumer database.
- **Surrogate collision on a populated database.** Allocate through the ledger and verify against
  the actual snapshot shape, as P2-44 required after 008 collided on ID 11.
- **Rollback.** Take verified snapshots first. Before publication, revert the revision. After
  publication the taxonomy addition stays (additive, soft lifecycle) and the fallback pointer is
  reverted in code; the 13 repaired rows can be re-categorized forward through the same
  event-emitting path.

## Outcome (fill in when done)
