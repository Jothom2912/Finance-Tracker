---
date: 2026-07-17
topic: F1-03 — learned corrections stored as auto-managed user rules, not merchant rows
status: active
---

# F1-03: learned corrections are RULES, not merchant-table rows

**Context.** The original F1-03 sketch (FEATURES.md) said a manual category correction
should "upsert a merchant mapping with `is_user_confirmed=true`". During the 2026-07-17
code survey this turned out to be the wrong storage: the `merchants` table is **global**
(`normalized_name` UNIQUE, no `user_id`) — one user's correction would rewrite another
user's categorization — and merchants don't feed the rule engine at all; a second matching
mechanism would have been needed.

## Decisions

1. **Corrections become auto-managed user rules.** The correction consumer
   (`category_corrected_consumer.py`) upserts into `categorization_rules`:
   `pattern_type=MERCHANT`, `pattern_value=<normalized full description>`,
   `user_id=<owner>`, `priority=10`, target `subcategory_id`; ON CONFLICT (partial unique
   index `(user_id, pattern_type, pattern_value)`, migration 007) updates the target.
   One matching mechanism (the rule engine), one storage, and learned rules appear in the
   F1-02 rules UI for free — visible + deletable keeps the user in control.
2. **Priority ladder 10/50/100**: 10 = learned from corrections, 50 = user-created
   (API clamps to [20,90] so users can't outrank learned rules or drop below seeds),
   100 = global seeds. `TieredRuleEngine` matches tiers in priority order with
   longest-match *within* a tier — user intent beats seed keyword length *across* tiers.
3. **Merchants table stays as global seed data**; `is_user_confirmed` and
   `MappingSource` stay unused (the original hook is superseded by this decision).
   No merchants-table schema changes.
4. **Event, not sync write**: transaction-service emits
   `TransactionCategoryCorrectedEvent` (v1, `transaction.category_corrected`) from the
   same condition that sets `categorization_tier="manual"`, via the outbox. The consumer
   only *writes rules*, never transactions — no event cycle is possible
   (`transaction.categorized` → tx-service is guarded by the manual-tier check).
5. **Parent-only corrections are skipped** (schema requires `subcategory_id`; a
   category-without-subcategory correction is logged at debug and not learned) —
   documented limitation, revisit only if it shows up in practice.
6. **Cache invalidation is API-process-only.** `RuleService` invalidates the per-user
   overlay cache in the API process; the **transaction consumer is a separate process**
   and picks up new/learned rules via its 60s TTL instead. Accepted: a transaction
   imported within ~60s of a rule change may still use the stale rule set (observed in
   the 2026-07-17 e2e; the next import categorizes correctly). Cross-process
   invalidation (bus message / shorter TTL) is deliberately not built for a
   single-user reality.

## Trade-offs accepted

- A learned rule keyed on the *full normalized description* is narrow (exact merchant
  string, not fuzzy) — deliberately conservative: false negatives (no learning for
  slightly-drifted descriptions) over false positives (over-broad rules the user didn't
  intend). F1-06's ML tier is the answer for fuzzy generalization.
- Rule rows accumulate per user; no pruning. Bounded by correction volume (≪ 100/user),
  and rows are visible/deletable in the UI.
