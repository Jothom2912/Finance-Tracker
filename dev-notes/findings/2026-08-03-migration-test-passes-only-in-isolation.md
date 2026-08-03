---
title: A migration test passed in isolation and failed in CI, because no local target ran the tree in one process
date: 2026-08-03
severity: MEDIUM
area: categorization-service, transaction-service, CI
status: resolved
backlog: []
resolved-by: commit fixing the fixture to rebind app.database and making test-all mirror CI
---

# A migration test passed in isolation and failed in CI

**Where**: `services/categorization-service/tests/migrations/test_alembic_upgrade.py`
(`TestTaxonomyRepair::test_same_run_id_is_idempotent`), `app/database.py:14`, and the `test-all`
targets in the categorization- and transaction-service Makefiles.

**Defect**: The test called `enqueue_repair`, which uses `async_session_factory` from
`app.database`. That module builds its engine **at import time** from settings, so the fixture's
`os.environ["DATABASE_URL"] = <container url>` only takes effect if nothing has imported
`app.database` yet. The test deferred its own import to inside the test body for exactly that
reason — but any test module that imports `app.main` during collection (most of
`tests/integration/`) freezes the factory on `localhost:5432` first. The result was a test that
passed alone and failed in company:

```
OSError: Multiple exceptions: [Errno 111] Connect call failed ('::1', 5432, 0, 0), …
```

**Why it went unnoticed**: neither local target could reproduce CI. `make test` runs
`pytest tests/ --ignore=tests/migrations`, so it never ran the test. `make test-migrations` runs
`pytest tests/migrations/`, where nothing imports `app.main`, so it passed. `make test-all` ran
those two as **separate pytest processes**, which reproduces neither. CI runs `uv run pytest tests`
— one process over the whole tree — and only that ordering exposes the dependency. The failure also
needed the TAX-06 commit to reach the remote before CI ever executed the test at all.

Attribution measured, not assumed: pairing the failing test with the **pre-existing**
`tests/integration/test_categorize_router_auth.py` reproduces it, so the pollution predates the
TAX-14 work that surfaced it.

**Fix**: the module-scoped `engine` fixture now rebinds `app.database.engine` /
`async_session_factory` to the container, and also patches modules that already did a
`from app.database import async_session_factory`, restoring both on teardown. Collection order no
longer decides the outcome. Both services' `test-all` became a single `uv run pytest tests`, with a
comment saying why two invocations are not equivalent.

Verified by control, not just by a green run: removing the rebinding brings the failure straight
back in the same pairing, so the fix is causal and the test still asserts real container data
(80 enqueued, 0 on repeat, 160 v3 events).

**Standing lesson**: a suite split across invocations cannot catch order dependence. When CI runs
one process, the local gate must too — otherwise "green locally" measures a different thing than
the gate it is supposed to predict.
