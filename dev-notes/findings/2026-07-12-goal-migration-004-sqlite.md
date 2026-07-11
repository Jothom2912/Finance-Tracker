---
id: F-2026-07-12-01
date: 2026-07-12
severity: LOW
area: goal-service
status: open
resolved-by:
---

# goal-service migration 004 is Postgres-only — sqlite migration tests are red

**Symptom:** `services/goal-service/tests/migrations/` — 1 failed + 5 setup errors:
`sqlite3.OperationalError: near "ALTER": syntax error` on
`ALTER TABLE goal_allocation_history ALTER COLUMN correlation_id TYPE VARCHAR(255)`.

**Cause:** `migrations/versions/004_widen_correlation_id_to_varchar.py` (commit
`462c8393`, pre-existing on master) uses `ALTER COLUMN ... TYPE` — Postgres syntax
sqlite cannot execute. The migration-test suite runs alembic `upgrade head` against a
sqlite tmp-file (`tests/migrations/test_adr_0003_goal_allocation_migration.py`
`migrated_engine` fixture), so every test that migrates to head now errors at setup.
Runtime (Postgres) is unaffected — the migration itself works in prod.

**Fix options:** (a) rewrite 004 with `op.batch_alter_table` (alembic's sqlite-safe
batch mode, works on both dialects); or (b) dialect-guard the statement. (a) is the
idiomatic alembic answer.

**Not fixed now because:** unrelated to the ES-integration work in flight; touching a
shipped migration deserves its own change + verification against a real Postgres.
