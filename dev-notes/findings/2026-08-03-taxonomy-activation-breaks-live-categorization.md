---
title: Taxonomy activation traded 130 working keyword rules for 82 rules, half of which can never fire
date: 2026-08-03
severity: HIGH
area: categorization-service, transaction-service, banking-service, taxonomy
status: open
backlog: [TAX-12, TAX-13]
resolved-by: null
---

# Taxonomy activation traded 130 working keyword rules for 82 rules, half of which can never fire

**Where**: `services/categorization-service/app/rule_engine_provider.py:219`,
`services/banking-service/app/adapters/outbound/enable_banking_client.py:295-320`, plus the 82
constrained seed rules installed by TAX-06.

**Defect**: Every transaction imported after the taxonomy activation lands on the absolute fallback
and is presented to the user as *Shopping*. Two independent causes, both measured on live data:

1. **42 of the 82 active rules are unreachable from the import path.** They carry
   `match_field='merchant'` (40 high-confidence + 2 medium) and cover exactly the large Danish
   chains — `netto`, `lidl`, `foetex`. But `transactions` has no `merchant` or `counterparty`
   column at all; its columns are `description`, `account_name`, `external_id` and financial
   fields. Transaction-service therefore always calls the categorizer with description-only, the
   evidence branch in `CategorizationService._run_pipeline` never fires, and a merchant-field rule
   can never match. The remaining 40 `match_field='description'` rules cover a different and much
   narrower set (`apotek`, `bager`, `pizzeria`, `zoo`, …) that excludes the big chains.
2. **The absolute fallback is `shopping_unspecified`.** `rule_engine_provider.py:219` hardcodes it,
   and the taxonomy has no unknown-purchase bucket to choose instead: the only typed unknowns are
   `unknown_transfer` (175) and `other_income` (168). So unmatched spending is not merely unlabelled,
   it is actively filed under a real spending category.

This is a **regression**, not a pre-existing gap. Measured against the retained TAX-10 pre-write
snapshot: before activation there were **130 system rules, all 130 active**, including
`keyword netto → subcategory 1`, which matched free-text descriptions and worked. After activation
there are 212 system rules of which only **82 are active** — the 130 legacy keyword rules are
deactivated and their replacement needs evidence the write model cannot supply.

**Why it matters**: 13 of the 14 transactions imported by the first sync after activation went to
`29/139` = `Shopping / Shopping — uspecificeret` at tier `fallback`, including groceries (NETTO,
LIDL, FOETEX), a subscription (OPENAI), and incoming person-to-person MobilePay transfers. The 14th
went to `35/164` `Indkomst / Offentlig støtte`, which is a confident wrong label on a private
transfer. Because the fallback is a real category, this silently inflates Shopping in budgets and
analytics instead of surfacing as unknown — the exact outcome product rule 4 of the taxonomy roadmap
("precision beats coverage; unknown data should reach a reviewable fallback") was written to prevent.
The roadmap's own typed review buckets (`Ukendt køb`, `Ukendt indbetaling`, `Ukendt overførsel`) were
never created.

It also belongs to the blind-instrument class: TAX-05 audited and counted 82 rules as coverage
without a check that a rule can fire through the real import path, so 42 dead rules passed as work
done. A coverage count over the rule table cannot see this; only a test that categorizes a realistic
bank description can.

**Note on scope**: TAX-10's historical remap is unaffected and correct — migrated transaction 827
reads `Transport / Offentlig transport`. This finding is about newly imported rows only.

**Suggested fix**: two separable pieces, and the second is worth doing regardless of the first.

- **Propagate merchant evidence.** The raw material already exists and is thrown away:
  `enable_banking_client.py` extracts `creditor_name` and `debtor_name` onto `BankTransaction`, then
  collapses both into one `description` for the downstream event. Carry them through the transaction
  event contract and schema as merchant/counterparty so the 42 merchant rules become reachable and
  the structured-evidence confidence model from
  [seed evidence and rule confidence](../decisions/2026-08-01-seed-evidence-and-rule-confidence.md)
  actually applies. Prefer this over relaxing the rules to free-text matching, which would discard
  that decision's precision guarantee.
- **Make the fallback honest.** Add typed unknown buckets additively and point the absolute fallback
  at the direction-appropriate one, so unknown spending reads as unknown. Direction is already
  available at categorization time via the amount sign.

Both change domain behavior across services and need an approved plan.
