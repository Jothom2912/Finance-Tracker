---
date: 2026-07-16
topic: P2-09 shipped — entry_reference + currency through saga import, dedup on (account_id, external_id)
---

# P2-09 — external_id + currency through the bank-sync saga

Phase 2's last code item. Plan was approved before implementation (3-service contract
change); design decisions + accepted artifacts recorded in
[decisions/2026-07-16-p209-dedup-semantics.md](../decisions/2026-07-16-p209-dedup-semantics.md).

## Done (4 commits)

- `9d80a7a6` **contracts**: `TransactionCreatedEvent` +`external_id`/`currency` (additive,
  version stays 1); `BulkImportTransactionsCommand` docstring documents item shape +
  `.get()` requirement; backwards-compat test (payload without the fields validates).
- `c8a1f8db` **transaction-service**: migration 012 (columns + partial unique index
  `(account_id, external_id) WHERE external_id IS NOT NULL`); three-way dedup in
  `bulk_import` (ext-id lookup, in-batch seen-set, NULL-scoped fuzzy fallback); new repo
  method `find_existing_external_ids` + `only_missing_external_id` flag on
  `find_existing_dedup_keys`; consumer normalizes ""/null external_id → None; fields on
  entity/DTO/response/all three event sites. 158 unit + 35 integration + 15 migration
  tests, ruff.
- `e913e44a` **banking-service**: fetch handler sends `external_id` (blank→None) +
  `currency` (fallback DKK) per item; EB client's present-but-null `.get()` chains
  hardened to `or`-chains. NEW test file locks the saga item contract for the first time.
  25 unit tests, ruff.
- (this commit) **dev-notes bookkeeping** + docker builds of both images.

## Verification

- All suites green per service (see commits). Migration test proves DKK backfill on
  pre-012 rows, UNIQUE+WHERE indexdef, IntegrityError on duplicate `(account_id,
  external_id)`, NULL duplicates still legal, downgrade-clean.
- Deploy order irrelevant (additive dict keys + server_default); NO RabbitMQ topology
  changes. saga-service untouched (pure pass-through of untyped items).
- E2E double-sync check (second sync → `duplicates_skipped == total`, 0 new rows) not run
  against a live EB connection this session — worth doing on next real sync.

## Found along the way (not P2-09 scope)

- `BulkCreateTransactionDTO.items` has `min_length=1, max_length=500`: an EB fetch with 0
  or >500 items makes `_handle_bulk_import` raise ValidationError → 3 retries → saga
  failure. Pre-existing; new backlog item P3-15.
- banking-service is not runnable test-wise on Python 3.14 locally (psycopg2-binary has no
  wheel); used `uv run --python 3.12` with dummy `DATABASE_URL`/`JWT_SECRET` env (settings
  fail fast per P1-06) — same shape as CI.

## Open ends

- F3-03 (multi-currency display) now unblocked: currency is stored + on events, but ES
  mapping, gateway GraphQL types and aggregations still assume DKK.
- external_id backfill for pending→booked transitions: known limitation, see decision note.
