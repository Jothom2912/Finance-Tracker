---
title: "Pattern: tiered categorization + feedback loop"
updated: 2026-07-17
source: categorization service doc; F1-02/03 plan + implementation 2026-07-17
---

# Tiered categorization + feedback loop

Categorization runs a **tier ladder** (rules → ML → LLM → fallback) with a **priority
ladder inside the rules tier**, and manual corrections feed back into learned rules.
Detail: [categorization-and-ai-services](../architecture/services/categorization-and-ai-services.md),
[plans/2026-07-17-user-rules-and-feedback-loop](../plans/2026-07-17-user-rules-and-feedback-loop.md).

## Two entry points, one engine

- **Sync tier-1**: transaction-service calls `POST /api/v1/categorize/` at create time
  (500ms budget, graceful degrade to uncategorized; caller's explicit category wins).
- **Async**: `transaction.created` → `transaction_consumer.py` → full pipeline → result +
  outbox `transaction.categorized` + inbox row in one transaction → tx-service consumer
  updates denormalized fields.

ML/LLM tiers are scaffolded but unwired (F1-06) — in practice: rules → fallback.

## Rules tier: priority ladder (F1-02)

`categorization_rules` (user_id NULL = global seed) with three priority bands:

| Priority | Meaning | Managed by |
|---|---|---|
| 10 | **Learned** from manual corrections (`pattern_type=MERCHANT`) | feedback consumer (auto) |
| 50 (20–90) | **User-created** KEYWORD rules via `/api/v1/rules` | user, RulesPage UI |
| 100 | **Global seeds** | migrations only |

Match order: priority tier asc, longest-match **within** tier — user intent beats seed
keyword length across tiers. `TieredRuleEngine` lives in the adapter layer;
`rule_engine_provider` caches the global engine + a TTL per-user overlay, invalidated by
`RuleService` on writes. Zero-rules path is byte-identical to the old global path.

## Feedback loop (F1-03)

1. Manual category change in tx-service `update_transaction` sets
   `categorization_tier="manual"` **and** outboxes `TransactionCategoryCorrectedEvent`.
2. `category_corrected_consumer.py` (own queue + DLQ + inbox) normalizes the description
   (pure domain function) and **upserts a learned user rule** (priority 10) — decided
   over merchant-table writes because `merchants` is global and doesn't feed the engine.
3. Learned rules are **visible + deletable** on RulesPage ("Lært af dine rettelser") —
   user stays in control.

No event cycle is possible: the consumer writes rules, never transactions, and
tx-service's categorized-consumer refuses to overwrite `tier="manual"` rows
(`is_user_confirmed` principle — automation never beats the user).

## Gotchas

- Only KEYWORD (API) and MERCHANT (learned) pattern types are live; REGEX/AMOUNT_RANGE
  are enum-only.
- Parent-only corrections (no subcategory) are skipped by the learner — documented
  limitation.
- The categorize endpoints are unauthenticated S2S (`user_id` in body) — audit MEDIUM,
  open.
- Danish transliteration/normalization lives with the engine — reuse it, don't re-implement
  ([import-dedup](import-dedup.md) has the same normalize-before-compare theme).
