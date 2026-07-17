---
title: "Pattern: import dedup"
updated: 2026-07-17
source: P2-09 decision 2026-07-16; live second-sync verification 2026-07-17
---

# Import dedup

Two import paths, two dedup identities — unified in transaction-service:

| Path | Identity | Mechanism |
|---|---|---|
| Bank sync (`bulk_import`) | `(account_id, external_id)` (EB `entry_reference`) | three-way rule + partial unique index |
| CSV (`import_csv`) | fuzzy `(user_id, account_id, date, amount, description)` | per-row SELECT before insert |

Authoritative rationale: [decisions/2026-07-16-p209-dedup-semantics](../decisions/2026-07-16-p209-dedup-semantics.md).
Verified live 2026-07-17: second sync skipped 214/214
([session](../sessions/2026-07-17-loose-ends-p315-chromadb-secondsync.md)).

## The three-way rule (`bulk_import`)

An item **with** an external_id is skipped iff:

1. `(account_id, external_id)` already exists, or
2. the same external_id repeats **within the batch** (EB pagination overlaps — without
   the in-batch set the whole flush dies on the unique index), or
3. *transition fallback*: its fuzzy key matches an existing row whose `external_id IS
   NULL` (pre-P2-09/CSV rows). A fuzzy match against a row with a **different**
   external_id does NOT dedupe — that was exactly audit-H10's false positive.

Items without an external_id (and all CSV rows) keep pure fuzzy behavior.

## Backstops & failure semantics

- Partial unique index `uq_transactions_account_external_id` on
  `(account_id, external_id) WHERE external_id IS NOT NULL` (migration 012).
- **IntegrityError = honest saga failure** — no `ON CONFLICT DO NOTHING`, because
  `bulk_create` must return real ids for outbox events + saga compensation accounting
  ([saga-orchestration](saga-orchestration.md)). Concurrent-saga race → step fails →
  re-sync dedupes cleanly (root fix = P3-14, serialize sagas per connection).

## Known accepted gaps (do not "fix" without reading the decision)

- Legacy fuzzy collapse and pending→booked id-never-backfilled: one-time transition
  artifacts, documented in the decision.
- Fuzzy key is sign/currency-blind — deliberately not widened.
- Same-day identical purchases without external_id still merge (CSV path) — inherent to
  the fuzzy key.
