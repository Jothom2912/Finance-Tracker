---
date: 2026-07-15
topic: Phase 2 resume after rate limit — in-flight wave-B work verified + committed; survey of what remains
---

# Phase 2 wave-B resume — status survey + fase 0 landed

Previous session was cut off by a rate limit mid-wave-B with four finished-but-uncommitted
units in the working tree. This session verified and committed them, fixed one
pre-existing test bug found along the way, and updated the stale BACKLOG.md P2 statuses.

## Done this session (all committed to master)

- `e2843727` **gateway wave-B**: local auth → `finans-tracker-auth` shim (optional-auth
  path translates `InvalidTokenError` → `None`), `app/shared/budget_period` deleted in
  favor of `finans-tracker-domain`, and the whole service migrated requirements.txt/pip →
  pyproject + uv.lock with a contracts-pattern Dockerfile. Verified: 23 unit tests, ruff,
  `docker build` from repo root.
- `5cfde6f0` **user-service wave-B**: local `PostgresOutboxRepository`/`RabbitMQPublisher`/
  worker logic deleted; shared `OutboxRepository`/`OutboxEventMixin`/`OutboxPublisherWorker`
  wired in. `OutboxEventModel` stays as a thin mixin subclass so Alembic metadata remains
  service-owned (matches migration 002 exactly). Verified: 32 unit tests, ruff, docker build.
- `02d1dba6` **P2-14 CI**: matrix +categorization/banking/saga/analytics; bandit
  `-ll -ii` hard-fail (nosec B104 added on gateway bind-all); e2e job polls health
  endpoints instead of `sleep 30`; `tests/e2e/conftest.py` aborts (exit 1) in CI when
  services unreachable so an all-skipped suite can't go green; root Makefile driven by one
  `PY_SERVICE_DIRS` list (11 services); `goal-service-ci.yml` deleted; analytics Makefile added.
- `946440c2` **categorization**: alembic `env.py` reads `DATABASE_URL` lazily from env
  (the documented extraction gotcha — import-time-cached Settings gave tests a stale URL);
  integration test updated to P2-06's provider-based consumer constructor. 13 integration
  tests green (testcontainers).
- `fee7a5ea` **pre-existing test bug fixed** (predates wave-B, verified via worktree at
  `b04fac72`): user-service integration conftest imported only `Base` from `app.database`,
  so `Base.metadata` was EMPTY when the first test's `create_all` ran — `app.models` was
  only imported later via `app.main` in the `client` fixture. First test in any run always
  failed with `no such table: users`; the rest passed off the module cache. Fix: explicit
  `from app import models` in conftest + `StaticPool` on the `:memory:` engine (each new
  pooled connection is otherwise its own empty DB). 16/16 green, also in isolation.
  **Lesson (generalizes)**: any service whose test conftest does `create_all` on
  `Base.metadata` must import its models module first — check this during each remaining
  messaging adoption, since the same conftest shape is copy-pasted across services.

## Wave-B adoption scoreboard (verified by grep, 2026-07-15)

| Package | Adopted | Remaining |
|---------|---------|-----------|
| auth | **ALL 10 (done 2026-07-15, this session's second half)** | — |
| messaging | user | account, budget, transaction, banking, goal, categorization, saga (7 — all still carry local `postgres_outbox_repository.py`/`rabbitmq_publisher.py` copies; consumer-base/DLQ migration = P2-19/20 lands here too) |
| domain (budget_period) | gateway | account (`app/shared/`), budget (`app/domain/`), analytics (`app/domain/`) (3) |

## Remaining plan (agreed with user)

1. **Fase 1 — auth sweep**: DONE later this session (commits f85dcb50..fe9a8ca5, one per service). Notable: categorization's missing-header response changed 403→401 (HTTPBearer dropped) and it now accepts user_id-only tokens; account-service's dead password/monolith code deleted with the swap; banking+account (pip-based) get the shared package via a `../shared/auth` path line in requirements.txt (cwd-relative: works from service dir locally/CI and from /app in Docker) — both images build and import auth.fastapi.
2. **Fase 2 — messaging** (M–L): one service at a time, user-service diff (`5cfde6f0`) is the
   template. Order by increasing complexity: goal → budget → categorization → banking →
   transaction → account → saga. Domain adoption (3 services) taken as cheap side work.
3. **Fase 3 — P2-09** alone (3-service contract change: `entry_reference`/`currency`
   through saga, dedupe on `(account_id, external_id)`), then **P2-15** (k8s secrets) anytime.

## Open ends

- gateway-service now has uv but its `test-integration` Makefile target references a
  `tests/integration/` dir that doesn't exist (target inherited from template) — harmless, tidy later.
- CI e2e job changes are committed but unproven until the next push to master/PR run.
- BACKLOG.md P1/P2 headers + row statuses refreshed this session; 2026-07-07 in-flight
  session log kept as history but superseded by this one.
