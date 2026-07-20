---
date: 2026-07-20
topic: F1-01 shipped — notification-service MVP (in-app feed for the 3 F1 auto-events)
---

# F1-01: notification-service MVP

Plan: [plans/2026-07-20-f101-notification-service-mvp.md](../plans/2026-07-20-f101-notification-service-mvp.md).
Built stub → full hexagonal service in 7 waves (A–G), commit-per-phase (~12 commits).

## Done

- **A** skeleton (uv/pyproject+lock, Dockerfile, config, database, alembic) + domain
  (Notification entity w/ computed is_read/is_dismissed, `uuid7` RFC 9562, Danish message
  builders) + `notifications` migration (UUIDv7 PK, unique `source_key`, soft-delete).
- **B** ports (`INotificationRepository`, `IEmailPort`, `IAccountOwnerPort`, `IUnitOfWork`)
  + Postgres repo/UoW + `LogEmailAdapter` (no-op) + `AccountServiceAdapter` (owner lookup).
- **C** `NotificationService` (3 handlers, source_key schemes, owner resolution, best-effort
  email) + `NotificationConsumer` (1 queue, 3 routing keys, IntegrityError→ACK, poison→DLQ).
- **D** REST feed API (list/unread-count/read/read-all/dismiss), JWT via shared auth,
  owner-scoped, 404 on foreign id.
- **E** frontend: `useNotificationFeed` hook (45s poll) + `NotificationBell` (badge, dropdown,
  mark-all, dismiss) in Navigation. **Distinct** from toast `useNotifications`.
- **F** compose (`postgres-notifications` 5441, service 8008, consumer) + CI matrix + Makefile.
- 45 backend tests + 3 frontend tests; ruff + bandit(0) + eslint + vite build clean.

## Live e2e (full stack): PASSED

- **goal-reached**: create goal → PUT to target → `goal.updated` → notification
  `goal.reached:19`; second PUT ⇒ **duplicate** (1 row). Danish body "…1.000,00 kr."
- **budget.month_closed**: create budget + `POST /monthly-budgets/close` → owner resolved
  (`GET /internal/accounts/18/owner` 200) → notification "juni 2026 … overskud 500,00 kr."
- **bank.sync.completed**: published a real event to the topic exchange (no PSD2 conn for
  the test user) → notification "3 transaktioner blev importeret."
- **API**: unread-count 3→2 (mark-read) → dismiss removes from feed → read-all → 0;
  a second fresh user sees 0 (JWT owner-scoping).

## Learned / gotchas

- **`goal.updated` never carries status="completed"** — it's the stored status
  (active/paused); completion is computed. Switched detection to `current >= target`.
  Bigger gap: the **allocation path emits no `goal.updated` at all** (its UoW has no
  outbox) → auto surplus→goal completion notifies nothing. → finding + **F1-08**.
- **Host port 5439 was taken** by `postgres-banking` — moved notifications to 5441.
  (Internal 5432 / DATABASE_URL unchanged.)
- `sa.Uuid` (not PG `UUID`) lets the same models + integration tests run on sqlite.
- alembic on sqlite: `create_unique_constraint` uses ALTER (unsupported) — put the unique
  constraint **inline** in `create_table`. And alembic.ini logger sections need `qualname`.
- `uuid7` isn't monotonic within one ms (random bits) → feed orders by `created_at` first.

## Open ends

- **F1-08**: emit event on allocation-completes-goal so the auto path notifies.
- Real email (SMTP) + reconsent banner still deferred; k8s manifests deferred with schedulers.
- e2e mutated the dev stack (user 17/18, goal 19, budget, notifications) — harmless.
