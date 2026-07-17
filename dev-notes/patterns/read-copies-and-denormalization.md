---
title: "Pattern: read-copies & denormalization"
updated: 2026-07-17
source: ADR-003; architecture audit 2026-07-07
---

# Read-copies & denormalization

Database-per-service forbids cross-service queries, so a service that *reads* another
context's data keeps a **local read copy**, maintained by consuming that context's
full-state events. On top of that, hot read paths denormalize *names* onto rows to avoid
N+1 lookups.

## Canonical case: taxonomy (ADR-003)

[docs/ADR-003-taxonomy-ownership-consolidated.md](../../docs/ADR-003-taxonomy-ownership-consolidated.md)
— categorization-service is the **sole taxonomy writer**. Never write categories from
another service.

1. Taxonomy CRUD in categorization-service (`category_api.py`, JWT) emits full-state
   `category.*` / `subcategory.*` events via outbox.
2. transaction-service's `taxonomy_sync_consumer` upserts them into local `categories` /
   `subcategories` read-copy tables
   ([transaction-service](../architecture/services/transaction-service.md)).
3. On transaction create, `category_name` / `subcategory_name` are denormalized onto the
   row **from the local read copies** — no HTTP call on the write path, no N+1 on reads,
   frontend independent of category-service.

Same mechanism elsewhere: banking-service's `accounts_projection` (from `account.*`
events; HTTP-seeded once — Fase 2 decision), and the ES documents in
[cqrs-es-read-store](cqrs-es-read-store.md) are the pattern at system scale.

## Rules that make it safe

- Events carry **full state**, consumers **upsert** → self-healing, order-tolerant
  ([idempotent-consumers](idempotent-consumers.md)).
- Denormalized fields are a **cache, not truth** — the owning service's DB wins. Accepted
  redundancy is the explicit trade-off (CLAUDE.md §Kategorisering).
- Frontend rule: fall back to ID-lookup if a denormalized name is missing — never crash
  on missing data.
- Distinguish from **stored-state-that-duplicates-computation** (anti-pattern): read
  copies replicate *another context's* truth; computed properties stay computed (e.g.
  goal status from `target_date` + `amount_saved`).

## Gotchas

- A stale read copy silently denormalizes stale names; there is no reconciliation job —
  the next full-state event heals it.
- `transaction.categorized` updates denormalized fields via consumer, but **manual
  corrections are pinned**: `categorization_tier="manual"` rows are never overwritten
  ([categorization-pipeline](categorization-pipeline.md)).
- The contracts README's event table drifts from reality — verify against
  `services/shared/contracts/contracts/events/` when adding consumers.
