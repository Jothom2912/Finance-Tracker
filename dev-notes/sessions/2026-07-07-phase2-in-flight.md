---
date: 2026-07-07 (status verified 2026-07-08)
topic: Phase 2 — partially complete, interrupted by usage limits. Verified status + resume plan.
---

# Phase 2 — status & resume plan

10 parallel agents implemented Phase 2; all were interrupted by session-limit then out-of-credits errors. On 2026-07-08 the coordinator (main) verified on-disk state cheaply (compile-checks + shared-package test runs) rather than relaunching agents. **Nothing is committed** — all work is in the working tree alongside the uncommitted P1 work.

## Verified facts (2026-07-08)

- **All changed/new Python across every service compiles clean** (`py_compile` over the full changed set — zero syntax errors; the only two flagged were the intentionally-deleted dead `shared/auth/jwt_utils.py` + its `__init__`).
- **Shared packages exist and their tests pass:**
  - `services/shared/domain` (`finans-tracker-domain`) — budget_period. **35 passed.** ✅
  - `services/shared/auth` (`finans-tracker-auth`) — jwt + fastapi dep; dead `jwt_utils.py` deleted. **28 passed.** ✅
  - `services/shared/messaging` (`finans-tracker-messaging`) — outbox/worker/rabbitmq/consumer/time/logging. **44 passed, 1 xfailed.** ✅ (the xfail is a documented in-memory-sqlite + task-cancellation harness race in `test_worker.py::test_survives_transient_errors_and_recovers`, NOT a worker defect — recovery logic verified correct; real fix noted in the test's xfail reason.)
- **Frontend P2-17 deletions happened**: 20 files deleted (the 3,534-line dead Budget module etc.).
- Per-service P2 edits are present and compile in: gateway (new `app/adapters/outbound/http_client.py` = shared AsyncClient helper), saga, transaction, categorization, banking, budget, goal, user, account, ai. **Their full test suites are NOT yet verified** (running all nine — several Docker/Testcontainers-dependent — was deferred to preserve budget).

## Known gaps to finish (next session, cheap first)

1. **No `MIGRATION.md` in any shared package** — the per-service adoption recipe was a deliverable; write it for messaging/auth/domain (contracts is the reference for the uv-path-dep + Dockerfile COPY mechanics). Until then, services still carry their own copies — **the shared packages are built but NOT yet adopted by any service** (that was the deferred "wave B" migration anyway).
2. **messaging package**: missing `README.md` and `uv.lock` (auth/domain have uv.lock). Add for install parity with contracts.
3. **transaction-service P2-05**: verify the composite-index Alembic migration was actually created (only the filter integration test was seen untracked; no new migration file spotted) — if missing, create it.
4. **Verify each service's suite** with its P2 changes: user, goal, budget, transaction, categorization, banking, gateway, saga, ai, account. Run per-service; treat Docker-dependent failures as infra, not code.

## Resume procedure

Per service: `git diff`/`git status` the paths → run its suite → done (green) / finish (partial) / redo (`git checkout --` the partial file). Backlog P2 rows are marked `needs-verification` where only compile is confirmed.

## Deferred (do NOT chase now)
P2-09 (external_id/currency through import — 3-service contract change, do alone), P2-15 (k8s secrets), wave-B adoption of the shared packages by services (needs gap #1 first).

## Still pending from Phase 1
Commit decision (nothing committed yet — P1 + P2 both in working tree); RabbitMQ queue delete/recreate for `account_service.account_creation`; AI re-ingest note; git-history rewrite decision for purged PII (C9).
