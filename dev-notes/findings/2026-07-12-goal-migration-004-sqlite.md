---
id: F-2026-07-12-01
date: 2026-07-12
severity: LOW
area: goal-service
status: resolved
resolved-by: F1-04 wave 0, 2026-07-17 (see plans/2026-07-17-f104-goal-allocation-completion.md)
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

**Resolution (2026-07-17, F1-04 wave 0):** Fix option (a) — migration 004 rewritten with
`op.batch_alter_table` (no-op wrapper on Postgres, table-recreate on sqlite). Two
*additional* root causes surfaced during the fix:

1. **The fixture migrated the wrong database.** `migrations/env.py` prefers
   `DATABASE_URL` over the alembic config's `sqlalchemy.url` (the deploy pattern from
   the service-extraction gotchas), and `tests/conftest.py:12` sets
   `DATABASE_URL=sqlite+aiosqlite:///:memory:` session-wide — so alembic upgraded a
   throwaway in-memory db while the tests queried the tmp file. Fixed by
   monkeypatching `DATABASE_URL` to the tmp-file URL (aiosqlite variant, since env.py
   imports `app.database` which builds an async engine) in both the `migrated_engine`
   fixture and the downgrade test.
2. **The downgrade was also broken on real Postgres** (pre-existing): varchar→uuid
   needs `postgresql_using="correlation_id::uuid"`; without it Postgres refuses the
   cast. Added — the cast still fails loudly if non-UUID source_keys exist, which is
   correct (downgrade is only possible before deterministic keys are written).

Verified: sqlite migration suite 6/6 green; throwaway `postgres:16` container ran
upgrade base→head, downgrade 004→003 (column back to `uuid`), re-upgrade →
`varchar(255)`. Full goal-service suite 67 passed + lint clean.
