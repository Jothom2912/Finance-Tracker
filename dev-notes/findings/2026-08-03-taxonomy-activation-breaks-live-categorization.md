---
title: Only 7 of 82 active rules are reachable from the import path, so new transactions all read as Shopping
date: 2026-08-03
severity: HIGH
area: categorization-service, transaction-service, banking-service, taxonomy
status: open
backlog: [TAX-12, TAX-13, TAX-14]
resolved-by: null
---

# Only 7 of 82 active rules are reachable from the import path

**Where**: `services/transaction-service/app/application/service.py:80`,
`services/transaction-service/app/adapters/outbound/categorization_client.py:50,84`,
`services/categorization-service/app/adapters/outbound/rule_engine.py:163`,
`services/categorization-service/app/rule_engine_provider.py:219`.

**Defect**: After the taxonomy activation, every imported transaction lands on the absolute fallback
and is presented as *Shopping*. Measured reachability of the 82 active seed rules from the normal
import path:

| Rules | Constraint | Reachable? |
|---|---|---|
| 33 | `match_field='description'`, `direction='outgoing'` | **No** — direction never matches |
| 42 | `match_field='merchant'`, `direction='outgoing'` | **No** — no merchant field exists |
| 7 | `match_field='description'`, `direction='incoming'` | Yes |

Three separate causes, in order of blast radius:

1. **Direction is derived from a sign that is never sent.** `transactions.amount` stores an unsigned
   magnitude with the direction in `transaction_type`, and `create_transaction` forwards
   `amount=float(dto.amount)` unchanged. `ConstrainedRuleEngine.match` computes
   `direction = "incoming" if amount > 0 else "outgoing" …`, so **every** transaction presents as
   incoming and all 75 outgoing rules are skipped. A/B control on the running service, same
   description, only the sign differing:
   `MobilePay Telenor … −299 → rule person_transfer` versus `+299 → fallback shopping_unspecified`.
   The bulk path has the same defect at `categorization_client.py:84`.
2. **42 merchant-field rules have no field to match.** `transactions` has no `merchant` or
   `counterparty` column — its columns are `description`, `account_name`, `external_id` and
   financial fields — so the evidence branch in `CategorizationService._run_pipeline` never fires and
   these rules, covering exactly the large chains `netto`, `lidl`, `foetex`, can never match.
   Verified: `NETTO 7760` falls back at either sign.
3. **The absolute fallback is `shopping_unspecified`**, hardcoded at `rule_engine_provider.py:219`,
   and the taxonomy has no unknown-purchase bucket to choose instead; the only typed unknowns are
   `unknown_transfer` (175) and `other_income` (168). Unmatched spending is therefore not merely
   unlabelled, it is filed under a real spending category.

**Why it matters**: 13 of the 14 transactions from the first sync after activation went to
`29/139 Shopping / Shopping — uspecificeret` at tier `fallback` — groceries, an OpenAI subscription
and person-to-person MobilePay both ways. The 14th matched one of the 7 reachable incoming rules.
Because the fallback is a real category, this silently inflates Shopping in budgets and analytics
instead of surfacing as unknown, which is what product rule 4 of the taxonomy roadmap ("precision
beats coverage; unknown data should reach a reviewable fallback") exists to prevent.

**This is a regression, and cause 1 was latent before it.** Measured against the retained TAX-10
pre-write snapshot: before activation there were **130 system rules, all active**, including
`keyword netto → subcategory 1`, which matched free text with **no direction constraint** — so the
unsigned amount did not matter and categorization worked. TAX-05/TAX-06 added direction constraints
to every rule, which converted a dormant contract mismatch into a total coverage collapse. The
sign has been unsigned on this path all along; nothing made it wrong until direction started to count.

It also belongs to the blind-instrument class: TAX-05 audited and counted 82 rules as coverage
without one test that a rule can fire through the real import path, so 75 unreachable rules passed as
work done. A count over the rule table cannot see this — only categorizing a realistic bank
description with a realistic amount can.

**Note on scope**: TAX-10's historical remap is unaffected and correct — migrated transaction 827
reads `Transport / Offentlig transport`. This finding concerns newly imported rows only.

**Suggested fix**: three separable pieces.

- **TAX-14 — make direction explicit** rather than inferred from a sign the caller does not send.
  Prefer sending the direction (or a signed amount derived from `transaction_type`) as part of the
  categorize contract, so the engine never has to guess. This is the smallest change with the largest
  effect: it restores 33 rules immediately. Any fix needs a test that categorizes through the real
  client, not a mock, or the same gap reappears.
- **TAX-12 — propagate merchant evidence.** The raw material already exists and is discarded:
  `enable_banking_client.py:295-320` extracts `creditor_name` and `debtor_name` onto
  `BankTransaction`, then collapses both into one `description`. Carrying them through the event
  contract and schema as merchant/counterparty makes the 42 merchant rules reachable and lets the
  confidence model in
  [seed evidence and rule confidence](../decisions/2026-08-01-seed-evidence-and-rule-confidence.md)
  actually apply. Prefer this over relaxing those rules to free-text matching, which would discard
  that decision's precision guarantee.
- **TAX-13 — make the fallback honest.** Add typed unknown buckets additively and point the absolute
  fallback at the direction-appropriate one. Worth doing regardless of the other two, because it is
  what makes the remaining coverage gap visible instead of mislabelled.

All three change domain behavior across services and need an approved plan.
