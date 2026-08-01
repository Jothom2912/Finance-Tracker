# Status — 2026-08-01

This is the bounded entry point for current work. The backlog owns priority and status; plan
outcomes own shipping narratives; findings and decisions own their durable facts.

## Active

No active implementation plan.

## Recently shipped

- **TAX-06** — additive 13/67 UUIDv7 taxonomy, 82 constrained rules, backward-compatible v3
  events and idempotent transaction/analytics read-copy repair; legacy assignments remain for
  TAX-07. [Plan + Outcome](plans/2026-08-01-tax06-additive-taxonomy-migration.md#outcome-fill-in-when-done).
- **TAX-04–05** — separated inactive seed manifests plus an executable 130-rule audit yielding
  82 provenance-bearing constrained rules; legacy migrations and runtime behavior remain pinned.
  [Plan + Outcome](plans/2026-08-01-tax04-tax05-seed-model-and-audit.md#outcome-fill-in-when-done).
- **TAX-01–03** — approved 13/67 purpose-first taxonomy, UUIDv7 + stable-key identity policy,
  complete 10/41 legacy mapping and executable baseline guard; no data migration performed.
  [Plan + Outcome](plans/2026-08-01-tax01-tax03-taxonomy-foundation.md#outcome-fill-in-when-done).
- **P3-46** — alle tre AI-modeller pulls deterministisk; med 16 GB Docker-memory gennemfører
  qwen3:8b-chatten rå SSE og Chromium-E2E uden OOM, med 62 stabile containere.
  [Plan + Outcome](plans/2026-08-01-p346-qwen8b-chat-e2e.md#outcome-fill-in-when-done).
- **P3-28** — guarded root Docker context, cache-free uv images and safe gzip/immutable asset
  delivery; representative goal image halved from 198.0 to 98.9 MB and live headers passed.
  [Plan + Outcome](plans/2026-08-01-p328-build-image-hygiene.md#outcome-fill-in-when-done).
- **P3-47** — `compose-check` now rejects location-local nginx headers that would silently
  shadow the perimeter's four security headers, with positive and negative parser controls.
  [Plan + Outcome](plans/2026-08-01-p347-nginx-header-inheritance-gate.md#outcome-fill-in-when-done).
- **P3-60 + P3-62** — honest 404/503 split for account → user, explicit temporary frontend
  error and one account lookup per goal creation; live negative smoke proved 503 + zero write,
  and the restored 62-container stack is healthy.
  [Plan + Outcome](plans/2026-08-01-p360-p362-upstream-error-honesty.md#outcome-fill-in-when-done).
- **P2-21 + P3-17** — Kubernetes workload parity and explicit migration ordering; clean and
  idempotent live rollout verified with zero workload restarts.
  [Plan + Outcome](plans/2026-08-01-p221-p317-k8s-parity-migration-ordering.md#outcome).
- **P2-43** — ugyldig goal-status afvises før write; migration 006 reparerer gamle værdier og
  håndhæver `active|paused` i databasen. [Plan + Outcome](plans/2026-08-01-p243-goal-status-integrity.md#outcome-fill-in-when-done).
- **F2-07** — ens budgetperiode på dashboard/kategoriside samt navngivne, linkbare
  over-budget-kategorier. [Plan + Outcome](plans/2026-08-01-f207-dashboard-period-budget-clarity.md#outcome-fill-in-when-done).
- **P3-65** — Codex discovery, bounded dev-notes retrieval and structural drift gates.
  [Plan + Outcome](plans/2026-08-01-p365-codex-dev-notes-optimization.md#outcome).
- **P3-59** — request-path logging and the rejection admission rule across the five previously
  silent API services. [Plan + Outcome](plans/2026-07-31-p359-request-path-logging.md#outcome-2026-07-31).
- **P3-57 + P3-58** — shared logging configuration in all API processes, including the
  account/Alembic reconfiguration trap. [Plan + Outcome](plans/2026-07-31-p357-api-logging-config.md#outcome).
- **F2-08** — user profile/password/username write path and frontend profile UI.
  [Plan + Outcome](plans/2026-07-29-f208-user-profile-write-path.md#outcome).

## Next candidates

- **TAX-07** — dry-run existing-data reclassification after TAX-06; preserve manual decisions
  and require separate approval before any bulk write.

## Blockers

No active blocker.

## Open findings to route first

- [Product-surface sweep](findings/2026-07-26-product-surface-sweep.md) — security, operations
  and UX follow-ups across the product.
- [Outbox port declares a foreign entity](findings/2026-07-27-outbox-port-declares-foreign-entity.md) — P2-32.
- [Goal has two runtime types](findings/2026-07-27-goal-entity-two-runtime-types.md) — P2-34 and
  the goal-service typecheck blocker.
- [Bare mocks hide contract drift](findings/2026-07-27-sync-trigger-double-value.md) — P3-41.

## Standing traps

- A command piped through `head`/`tail` reports the last process's status unless pipe failure is
  handled explicitly; capture the command's real exit code.
- Restart app services after recreating datastores before diagnosing closed pooled connections
  as a code regression.
- Loopback-bound datastores are less exposed, not authenticated; containers can still reach the
  host and credentials remain development defaults.
- `docker compose ps` can show exit code 0 while a worker is restarting. Use
  `make compose-state-check`, which checks state as well as exit code.
- `curl` proves transport, not browser-client behavior. Keep a client-level or browser test for
  libraries that parse or construct URLs.
- A mocked dependency can be the blind spot; pair it with a focused test that exercises the
  real boundary when that behavior matters.
- A green static `make check` does not prove a container imports or starts under image
  dependencies. Start/import the affected API and worker modules.
- `make notes-check` proves structure and retrieval budgets, not the truth of dated claims;
  verify those against current code.
