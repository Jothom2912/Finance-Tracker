---
title: TAX-14 — make categorization direction explicit instead of inferred from a sign
date: 2026-08-03
status: open
backlog: [TAX-14]
related:
  - ../findings/2026-08-03-taxonomy-activation-breaks-live-categorization.md
  - 2026-08-03-tax13-honest-unknown-fallback.md
  - 2026-08-01-tax07-existing-data-reclassification-dry-run.md
  - 2026-08-01-tax10-approved-existing-data-reclassification.md
  - ../decisions/2026-08-01-seed-evidence-and-rule-confidence.md
---

# TAX-14 — make categorization direction explicit instead of inferred from a sign

## Goal

The rule engine must be told whether money came in or went out instead of guessing it from the sign
of an amount that no caller signs. Done means: every producer of a categorize request passes an
explicit direction, the engine never infers one, all four call paths are covered by a test that runs
through the real client rather than a mock, and the 33 outgoing description rules match again —
verified by categorizing the seven real bank descriptions from the finding and getting rule-tier
results instead of the Shopping fallback.

## Context

[The reachability finding](../findings/2026-08-03-taxonomy-activation-breaks-live-categorization.md)
measured that only 7 of 82 active rules can fire, and this plan is cause 1 — the largest of the three.
`transactions.amount` stores an unsigned magnitude with the direction in `transaction_type`, while
`ConstrainedRuleEngine.match` computes `direction = "incoming" if amount > 0 else "outgoing" …`. Every
row therefore presents as incoming and all 75 outgoing rules are skipped. A/B control on the running
service, same description and only the sign differing: `MobilePay Telenor … −299 → rule
person_transfer` versus `+299 → fallback shopping_unspecified`.

The mismatch was harmless until TAX-05/TAX-06 put a direction constraint on every rule; the old
keyword rules had none, so the unsigned amount never mattered. That is why this reads as a regression
even though the sign has been unsigned on this path all along.

**Four producers** all send the unsigned amount, and two of them matter beyond new imports:

| Producer | Site |
|---|---|
| Sync create | `transaction-service/app/application/service.py:80` |
| Bulk import | `transaction-service/app/application/service.py:530` |
| Async consumer | `categorization-service/app/workers/transaction_consumer.py:119-123` |
| TAX-07/TAX-10 evidence | `transaction-service/app/application/reclassification.py:269,277` |

The fourth is the uncomfortable one: TAX-07's evidence resolution asked the categorizer with an
unsigned amount **and** derived its recorded `direction:` reason code from the same unsigned value, so
every evidence row was resolved as if incoming. That means **10 of the 220 rows TAX-10 already wrote**
— the constrained-rule proposals to `own_accounts_savings` — were derived under a direction that was
always wrong, and the `direction:` strings in the retained reports are uniformly "incoming". The 527
unresolved rows were also judged under that handicap, so some may resolve cleanly once direction is
right. Nothing was corrupted: the writes were hash-approved and idempotent, and the 527 were never
touched. But the evidence needs re-deriving, which is scoped here as a follow-up, not a silent fix.

The async path needs no contract change: `transaction.created` already carries `transaction_type`
alongside `amount` — the consumer simply ignores it.

## Non-goals

- No merchant/counterparty propagation (TAX-12) and no new taxonomy nodes or fallback change (TAX-13).
- No change to the 82 seed rules, their constraints, confidences or provenance. This plan makes
  existing rules reachable; it does not retune them.
- No change to how `transactions.amount` is stored. The unsigned-magnitude-plus-`transaction_type`
  representation stays; only what we *send* to the categorizer changes.
- No re-run of the TAX-07 dry run or repair of the 10 evidence-derived rows inside this plan. This
  plan measures and reports the delta; acting on it needs its own approval, since any write to those
  rows is a taxonomy bulk write.
- No retroactive re-categorization of historical rows beyond that measurement.
- No inference fallback. If direction is missing the engine must not guess from the sign again.

## Steps

1. [ ] **Put direction in the contract as a required field.** Add
   `direction: Literal["incoming", "outgoing"]` to `CategorizeRequestDTO` in
   `categorization-service/app/application/dto.py`. Required, not optional-with-sign-fallback: an
   optional field that silently degrades to the old inference is how this defect survived, and the
   endpoint is internal-only (`require_internal_api_key`) with four in-repo callers, so a required
   field is a compile-and-test-time break rather than a production surprise. Reject a request whose
   direction contradicts a non-zero signed amount, so a caller cannot pass both inconsistently.
2. [ ] **Stop inferring in the engine.** In
   `categorization-service/app/adapters/outbound/rule_engine.py`, take direction as a parameter
   instead of deriving it at line 163. Keep `absolute_amount` derived from `abs(amount)` for the
   min/max constraints — that part was always sign-independent. Thread it through
   `CategorizationService._run_pipeline`, both `match` overloads and the user-overlay engine.
3. [ ] **Update all four producers.** `service.py:80` and `service.py:530` derive direction from
   `dto.transaction_type` / the batch item's type; `transaction_consumer.py` reads the
   `transaction_type` already present in the event payload; `reclassification.py:269` sends the
   explicit direction and `:277` stops recomputing it from the unsigned amount. Extend
   `CategorizationClient.categorize`/`categorize_batch` and the `EvidenceCategorizerPort` protocol so
   the type system forces every call site to supply it.
4. [ ] **Test through the real boundary, not a mock.** The gap survived because the seed audit counted
   rules in a table and the client was mocked. Add: an integration test that drives
   `CategorizationClient` against the real categorize router for both directions; a unit test per
   producer asserting the direction it sends for an expense and an income row; and a reachability
   guard asserting that **every active seed rule's direction is satisfiable by some producer**, so a
   future rule set that no caller can reach fails the suite instead of shipping. Assert the seven
   real descriptions from the finding — `NETTO 7760`, `LIDL181KBHLYGTEN`, `FOETEX NOERREBRO`,
   `OPENAI *CHATGPT SUBSCR`, `MobilePay Telenor …`, `MobilePay Adam Fischer Duffus`,
   `Fra INGER KRISTENSEN` — noting that the three chains stay on fallback until TAX-12, which is the
   expected and documented split between the two plans.
5. [ ] **Measure, then report the historical delta.** With direction correct, re-run the TAX-07
   scanners read-only against a disposable copy and diff the dispositions against the retained
   `tax10-20260801-prewrite` manifests: how many of the 527 unresolved now resolve, and whether any of
   the 10 evidence-derived rows TAX-10 wrote would now get a different target. Record the counts in
   this plan's Outcome and, if the delta is non-empty, open a follow-up item. Do not write.
6. [ ] **Verification.** `make -C services/categorization-service test check`,
   `make -C services/transaction-service test check`, focused analytics projection tests,
   `make compose-check`, `make notes-check`, `git diff --check`. Then live: import or re-categorize a
   known outgoing transaction through the running stack and confirm it lands on a rule tier, and
   confirm the 13 rows currently at `29/139` change only if a rule now matches them.

## Risks & rollback

- **A producer is missed and silently degrades.** Mitigated by making the field required so a missing
  argument is a type/test error, not a runtime default. Detect with the per-producer tests plus a log
  on any rejected request.
- **Direction and stored sign disagree for real data.** Some rows may carry a negative amount with
  `transaction_type='income'` or vice versa. Measure the distribution before step 3 and decide
  explicitly which field wins; the contract check in step 1 must not start rejecting legitimate
  existing rows. If such rows exist, they are a separate data-integrity finding.
- **Suddenly-matching rules move analytics.** Newly matched rows change category assignment for new
  imports; that is the intended fix, but verify per-category before/after counts and totals so the
  signed DKK total stays identical.
- **The historical delta is large.** Step 5 may show that many of the 527 now resolve. That is an
  opportunity, not a regression, and it must not be written under TAX-10's old approval — those
  hashes covered a different evidence set.
- **Rollback.** Code-only change with no migration and no data write, so revert the commit. Nothing in
  this plan mutates a database; step 5 runs against a disposable copy.

## Outcome (fill in when done)
