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
- **Root `make check` was red on master before P2-09** — swept clean this session:
  ruff-format drift in user/transaction/categorization/banking/gateway/saga (3 style
  commits, all affected suites re-run green) and a bandit B110 (silent except-pass) in
  account-service `database.py` (fixed with a debug-log, `b221c907`).
- **Bandit config divergence, unresolved**: CI runs `bandit -r app -x tests -ll -ii`
  (P2-14), but account/banking/gateway Makefiles run bare `bandit -r app -x tests` —
  the local gate is STRICTER than CI and will hard-fail on any future Low finding.
  Aligning the Makefile flags with CI was deliberately left to a user decision (it reads
  as loosening a security gate). Either add `-ll -ii` to the three Makefiles or accept
  divergence.
- Local `make check` for the pip-based services (account, banking) additionally needs
  `ruff`/`bandit`/`pytest` on PATH (`uv tool install ruff bandit`; pytest ran via
  `uv run --with-requirements` instead). CI installs these explicitly.
- goal-service `make test` is red on the KNOWN open finding (migration 004 Postgres-only
  vs sqlite migration tests, [findings/2026-07-12-goal-migration-004-sqlite.md](../findings/2026-07-12-goal-migration-004-sqlite.md)) —
  unrelated to P2-09. All other 10 services' suites verified green this session
  (user 32, tx 158+35+15, cat 51, account 22, budget 42, gateway 23, ai 98, banking 25,
  saga 49, analytics 122, contracts 39+2).

## Live-smoke fallout: wave-B saga regression found & fixed (`e76bc896`)

First live sync after the stack restart 404'd on saga-status polling. Root cause was NOT
P2-09: the P2-01 wave-B port of saga-service wired shared `messaging.OutboxRepository`
directly in as the `IOutboxRepository` port implementation, but the orchestrator's two
`outbox.add(...)` call sites use the port's dict signature (`event_type=`, `payload_json=`,
…) → `TypeError` inside `start_saga` → saga instance never created → every bank sync dead
since the wave-B rollout. All 49 unit tests were green because the in-memory fake
implements the *port*, not the wired adapter — textbook "unit-tested handler ≠ working
event path". Fix: `SagaOutboxAdapter` (adapter layer) satisfies the port and translates to
the shared `add(event, …)` via a `SerializableEvent` envelope; port/orchestrator/tests
untouched. NEW `test_saga_outbox_wiring.py` drives the orchestrator through the REAL
`SQLAlchemyUnitOfWork` on sqlite so this seam is covered from now on. **Lesson for the
remaining wave-B surface: any service where a shared-package class was wired directly as a
port implementation should get one real-UoW wiring test.**

## Live-smoke fallout #2: same wave-B bug class in transaction-service (`7674de13`+`9021d877`)

Retry after the saga fix got further — banking fetched 212 transactions (step 0 OK,
P2-09 fields flowing) — then the import step crashed: `OutboxRepository.add_batch()
missing 2 required positional arguments`. Same root cause as the saga regression: the tx
port's `add_batch` takes per-entry `(event, aggregate_type, aggregate_id)` tuples (every
imported transaction is its own aggregate), the directly-wired shared repo binds ONE
aggregate to all events. **Both bulk paths (CSV import + bank-sync bulk import) were dead
since wave-B**; single-creates worked, masking it. The saga failed honestly at the import
step — P1-12 semantics working as designed.

Fix: new `add_entries` (per-entry batch) in shared messaging + `TransactionOutboxAdapter`
implementing the port on top of it; wiring test drives `bulk_import` through the real UoW
on sqlite. Audited ALL other services' outbox call sites: budget/banking/categorization/
goal/user use `add(event=…, aggregate_type=…, aggregate_id=…)` which matches the shared
signature — only saga + transaction had mismatches, both now fixed and wiring-tested.

**Deploy gotcha (cost one debugging round):** every consumer/worker compose service has
its OWN `build:` block → own image tag. `docker compose build <api-service>` does NOT
refresh the consumers — they force-recreate onto their stale images. Rebuild the full
per-service image family (e.g. `saga-start-consumer`, `transaction-saga-command-consumer`)
whenever service code changes.

## Live e2e verification (real EB connection, 2026-07-16)

Replayed the DLQ'd `saga.bank_sync.start` (correlation `8268295a…`) after all images were
rebuilt: saga `completed` through all 3 steps — `total_fetched: 212, new_imported: 5,
duplicates_skipped: 207, errors: 0`. The 207 skips are the transition fallback matching
pre-P2-09 history (external_id IS NULL); the 5 new rows all carry `external_id` +
`currency`. P2-09 verified end-to-end against the live bank. (Second-sync dedup-on-id
check: next sync should skip all 212.)

## Open ends

- F3-03 (multi-currency display) now unblocked: currency is stored + on events, but ES
  mapping, gateway GraphQL types and aggregations still assume DKK.
- external_id backfill for pending→booked transitions: known limitation, see decision note.
