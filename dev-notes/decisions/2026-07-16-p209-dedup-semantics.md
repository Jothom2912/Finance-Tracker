---
date: 2026-07-16
topic: P2-09 dedup semantics — external_id key, transition fallback, IntegrityError backstop
status: active
---

# P2-09: bank-import dedup on (account_id, external_id)

**Context.** Audit H10: Enable Banking's `entry_reference` and `currency` were dropped in
banking-service's fetch handler, so re-sync dedup relied on the fuzzy key
`(account_id, date, amount, description)` — wrongly merging identical same-day purchases
and duplicating rows on description drift. P2-09 carries both fields through the saga and
dedupes id-bearing imports on `(account_id, external_id)`.

## Decisions

1. **Three-way dedup rule in `bulk_import`** (transaction-service `service.py`):
   an item WITH an external_id is skipped iff (a) `(account_id, external_id)` exists,
   (b) the same external_id repeats within the payload (EB pagination can overlap — without
   the in-batch set the whole flush would die on the unique index), or (c) — *transition
   fallback* — its fuzzy key matches an existing row **whose external_id IS NULL**
   (pre-P2-09/CSV rows). A fuzzy match against a row with a *different* external_id does
   NOT dedupe: that is precisely H10's false positive, fixed going forward. Items without
   an external_id keep the pure fuzzy behavior — `import_csv` untouched.
2. **Partial unique index** `uq_transactions_account_external_id` on
   `(account_id, external_id) WHERE external_id IS NOT NULL` (migration 012). This is the
   "origin marker" migration 011's docstring said was missing; 011's non-unique fuzzy
   index stays. `user_id` is not in the key — accounts are single-owner ints.
3. **IntegrityError = honest saga failure, no ON CONFLICT rewrite.** `bulk_create` must
   return entities with ids for outbox events + `imported_ids` (saga compensation);
   `ON CONFLICT DO NOTHING RETURNING` would silently drop rows from that accounting.
   A concurrent-saga race hits the unique index → step replies failure (P1-12) → re-sync
   dedupes cleanly. P3-14 (serialize sagas per connection) remains the fix for the race itself.
4. **`currency String(3) NOT NULL DEFAULT 'DKK'`** — whole app is implicitly DKK; the
   server default backfills existing rows and keeps the manual-entry path unchanged.
   Read-side display/aggregation is F3-03 (ES mapping + gateway deliberately untouched).
5. **`TransactionCreatedEvent` keeps `event_version=1`** with additive optional
   `external_id`/`currency`: all consumers are pydantic `extra='ignore'` or raw-dict
   readers; the v2 precedent (TransactionCategorizedEvent) was behavior-bearing, this is not.
6. **Saga item dicts stay untyped** (`items: list[dict]` in contracts) — they round-trip
   through JSON `context_json`, so a typed model would never be instantiated on the consume
   path. Shape documented in `BulkImportTransactionsCommand`'s docstring; consumers read
   with `.get()` + defaults, making deploy order irrelevant.

## Accepted transition artifacts (documented, not engineered around)

- **Legacy fuzzy collapse**: two distinct incoming id-bearing items can both fuzzy-match one
  pre-P2-09 row and both be skipped — identical to pre-P2-09 behavior, one-time window.
- **Pending→booked**: EB pending transactions often lack entry_reference; imported with
  external_id NULL, the later booked re-fetch is caught by the legacy fallback but the id is
  never backfilled. No duplicate arises; backfill would be a follow-up.
- **Sign/currency blindness in the fuzzy key** (refund vs purchase of same magnitude;
  foreign-currency vs DKK same-magnitude): pre-existing in all import paths, only relevant
  for the legacy fallback window; `DedupKey` deliberately not widened.
- **Description drift** re-imports drifted legacy rows only if `date_from` reaches back
  before the last sync — normal incremental syncs don't.
