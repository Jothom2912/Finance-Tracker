# Account-Service Follow-ups

Items deferred from the account-service extraction (phases 1-5, completed 2026-05-08).

## Open

### Delete dead `backend.account.*` code in monolith

The monolith still contains the old `backend/account/` directory tree (domain,
adapters, DTOs). All imports were removed in phases 4-5 and the routes are
gone. The files are inert but clutter the repo.

**Action:** Run `rg "from backend.account|import backend.account"` across the
monolith. If zero hits, delete the entire `services/monolith/backend/account/`
directory. If references remain, trace and decide per-file.

**Priority:** Low. Cosmetic debt, no runtime impact.

---

### Investigate `monolith.transaction_sync.dlq` (156 messages)

Observed during Phase 5 queue inspection (2026-05-08). The
`monolith.transaction_sync.dlq` queue contains 156 dead-lettered messages.
Unknown whether these represent real data loss or historical noise from
development.

**Action:** Inspect a sample of messages (payload, timestamps, error reason).
Determine if they are recoverable and whether the root cause is still active.

**Priority:** Medium. If these are failed transaction sync events, there may be
MySQL projection drift.

---

### DLQ monitoring across all queues

No automated alerting exists for dead-letter queues. Messages accumulate
silently.

**Action:** Add a simple monitoring mechanism — either a Makefile target that
prints DLQ counts, a cron job, or a health-check endpoint that warns when any
DLQ has messages above a threshold.

**Priority:** Low for dev, medium for production.

---

### Account group tests need migration to account-service

BVA tests for `AccountGroupsCreate` were removed from the monolith
(`test_bva_additional_models.py`) because the DTO moved to account-service.
They should be re-implemented in `services/account-service/tests/`.

**Priority:** Low. The DTO validation logic is unchanged; only the test
location needs updating.

---

## Completed

### Full extraction (phases 1-5) — 2026-05-08

- Port conflicts resolved (ai-service 8004 to 8007, postgres-budget 5436 to 5437)
- Data migrated from MySQL to Postgres (idempotent script)
- Transactional outbox pattern implemented (sync repositories, async publisher)
- AccountSyncConsumer keeps MySQL read-replica in sync
- Frontend cutover to account-service port 8004
- Account routes removed from monolith
- New account-creation consumer replaces monolith's old consumer
- Partial unique index enforces default account idempotency
- Old consumer stopped, old queue deleted
- Makefile updated with `postgres-account` and `dev-account-service`

Commits: `a7b9f9d`, `bb68770`
