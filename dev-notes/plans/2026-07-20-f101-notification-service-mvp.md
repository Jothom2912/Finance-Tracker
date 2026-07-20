---
title: "F1-01: Notification service MVP — in-app feed for auto-events"
date: 2026-07-20
status: open            # open | in-progress | done | superseded
backlog-items: [F1-01]
related:
  - ../backlog/FEATURES.md
  - ../sessions/2026-07-17-f105-scheduled-sync.md   # deferred reconsent/auto-sync notifications here
  - ../patterns/idempotent-consumers.md
  - ../decisions/2026-07-13-embed-worker-placement.md  # own-queue isolation rule
---

# F1-01: Notification service MVP

## Goal

Turn the empty `notification-service` stub into a real hexagonal service that consumes
the auto-events the F1 chain now produces and surfaces them as a **per-user in-app feed**
(bell + unread badge + dropdown in the frontend). Done when: an auto bank-sync, a
month-close with surplus, and a goal reaching 100% each produce exactly one notification
for the owning user, visible in the feed, markable-as-read, and idempotent under
redelivery (proven by service tests + a live e2e).

Two scope decisions taken up-front (user, 2026-07-20):
- **Email deferred** — build the in-app feed fully; email is an `IEmailPort` with a
  log/no-op adapter so SMTP can be wired later without refactoring.
- **v1 triggers** = `bank.sync.completed`, goal-reached (`goal.updated` → status
  `completed`), `budget.month_closed`. **Not** `transaction.categorized` (noisy, no value).

## Context

F1-04/05/07 shipped the fully-automatic ADR-0003 chain (nightly sync → day-7 close →
surplus → goal allocation). Those run without the user watching, so they need to be
*told*. F1-05 explicitly deferred the auto-sync notification + reconsent banner to F1-01
(they are currently only WARNING logs). All three trigger events already flow on the
RabbitMQ topic exchange; the stub service (port 8008) and the consumer infra
(`shared/messaging` `ConsumerBase` with DLQ+retry+inbox) already exist, so this is
wiring + a feed UI, not new plumbing.

Grounding facts verified in code (2026-07-20):
- Stub is health-only: `services/notification-service/app/main.py` + placeholder
  `application/service.py`, empty `domain/`, `adapters/`, `ports/`. No DB, no requirements
  beyond fastapi. README mentions a `budget.threshold.80pct` event — **stale/aspirational**;
  that event does not exist (it belongs to F2-03) — ignore it.
- Event shapes (`services/shared/contracts/contracts/events/`):
  - `BankSyncCompletedEvent` (`bank.sync.completed`): carries `user_id`, `connection_id`,
    `account_id`, `new_imported`, `duplicates_skipped`, `errors`. Self-contained.
  - `GoalUpdatedEvent` (`goal.updated`): carries `user_id`, `goal_id`, `name`,
    `target_amount`, `current_amount`, `status`. Fires on **every** goal edit — must filter
    to the transition into `status == "completed"` (`GoalStatus.COMPLETED`, see
    `goal-service/app/domain/entities.py`).
  - `BudgetMonthClosedEvent` (`budget.month_closed`): **no `user_id`** — only `account_id`,
    `year`, `month`, `surplus_amount`, and a deterministic `source_key` property. Owner must
    be resolved via account-service.
- Owner resolution already exists and is proven: goal-service's
  `AccountServiceAdapter.get_owner_user_id(account_id)` →
  `GET {ACCOUNT_SERVICE_URL}/api/v1/internal/accounts/{id}/owner` with header
  `x-internal-api-key`. Copy this adapter verbatim.
- Consumer infra: `messaging.ConsumerBase` — own queue + DLX/DLQ, header-based retry to
  own queue, `PoisonMessageError` → DLQ, optional `InboxDeduplicator` (message_id =
  `correlation_id`). Reference consumer: `goal-service/app/workers/budget_month_closed_consumer.py`.
- Idempotency house-style = deterministic `source_key` + unique constraint (goal-service),
  not app-logic. We reuse that.
- Frontend: per-service API clients (`src/api/*.jsx` via `crudFactory`), service URLs in
  `src/config/serviceUrls.js` (+ `.env.example`), `apiClient` auto-attaches JWT +
  `X-Account-ID`. **Name clash warning**: `src/context/NotificationContext.jsx` already
  exports `useNotifications` — but it is a *transient toast* system (success/error, auto-
  dismiss), unrelated to this feed. Do NOT touch it; name the feed hook differently
  (`useNotificationFeed`).
- Compose shape per service = `postgres-<svc>` + API container + one container per worker
  (`command: ["python","-m","app.workers.<x>"]`), `DATABASE_URL` asyncpg, `INTERNAL_API_KEY`,
  `JWT_SECRET`, healthcheck. See goal-service block (`docker-compose.yml:152-234`).

## Non-goals (functionality preserved / explicitly out of scope)

- **No real email/SMTP** — `IEmailPort` + no-op(log) adapter only. Real delivery is a follow-up.
- **No push notifications** (F3-04) and **no PWA** work.
- **Do not modify** the frontend toast `NotificationContext`/`useNotifications` — it stays
  exactly as-is; the feed is additive.
- **No new events emitted** by notification-service in v1 → no outbox worker, no producer.
- **No budget 80%-threshold alert** — that needs a new budget-service event; it is F2-03.
- **No reconsent-banner UI** beyond surfacing whatever bank-sync notification carries; the
  richer reconsent flow stays a follow-up (needs a consent-expiry event/field).
- **No change to any producer** (banking/goal/budget services) — read-only consumption.
- k8s manifests for the new service/consumer are **deferred** (bundled with the schedulers'
  deferred manifests at next k8s work) — compose only in v1.

## Steps

### A. Service skeleton & persistence  ✅ done 2026-07-20
1. [x] `services/notification-service/` — bring up to house-standard: `pyproject.toml`/
   `uv.lock` (mirror goal-service deps: fastapi, uvicorn, sqlalchemy[asyncio], asyncpg,
   alembic, pydantic v2, aio_pika, httpx + the three shared local packages
   `finans-tracker-{messaging,auth,contracts}`), real `Dockerfile` (copy shared packages,
   port 8008), `app/config.py` (DATABASE_URL, RABBITMQ_URL, JWT_SECRET, ACCOUNT_SERVICE_URL,
   INTERNAL_API_KEY, CORS_ORIGINS), `app/database.py` (async_session_factory), `Makefile`
   (test target). Delete stale README claims; rewrite README to match reality.
2. [x] Domain (`app/domain/`): `Notification` entity + `NotificationType` enum
   (`BANK_SYNC_COMPLETED`, `GOAL_REACHED`, `BUDGET_MONTH_CLOSED`). **Pure message-builder
   functions** (Danish title/body per type from event fields) — this is the testable domain
   logic. e.g. `build_bank_sync_message(new_imported, errors) -> (title, body)`. No I/O, no
   `datetime.now()` (inject clock / take timestamp from event).
3. [x] Models + migration: `app/models.py` `notifications` table — `id` UUIDv7 PK,
   `user_id int`, `type`, `title`, `body`, `source_key` (unique, NOT NULL), `read_at`
   nullable, `dismissed_at` nullable (soft-delete), `created_at`. Alembic `migrations/`
   with `env.py` reading `DATABASE_URL` (asyncpg→psycopg2 swap — the gotcha from CLAUDE.md)
   and `versions/001_create_notifications.py`. Unique index on `source_key` = idempotency backstop.

### B. Ports & adapters  ✅ done 2026-07-20
4. [x] `app/application/ports/outbound.py`: `INotificationRepository`
   (`add(notification) -> None` raising on dup source_key, `list_for_user(user_id, unread,
   limit, offset)`, `unread_count(user_id)`, `mark_read(id, user_id)`, `mark_all_read(user_id)`,
   `dismiss(id, user_id)`, `source_key_exists(key)`), `IEmailPort` (`send(user_id, title,
   body)`), `IAccountOwnerPort` (`get_owner_user_id(account_id) -> int`). Inbound port =
   application service protocol.
5. [x] Adapters: `adapters/outbound/postgres_notification_repository.py` +
   `unit_of_work.py`; `adapters/outbound/log_email_adapter.py` (no-op that logs at INFO);
   `adapters/outbound/account_adapter.py` (copy goal-service's `get_owner_user_id`);
   domain exceptions (`AccountOwnerUnavailable`) with HTTP mapping in the API layer.

### C. Application service + consumer (the event path)  ✅ done 2026-07-20
6. [x] `app/application/service.py`: `NotificationService` — one `create_from_event`-style
   method per trigger, each computing the deterministic `source_key`, resolving user_id
   (direct for bank/goal; via `IAccountOwnerPort` for budget), building the Danish message,
   persisting (idempotent), then best-effort `IEmailPort.send`. `source_key` scheme:
   - bank sync: `bank.sync.completed:{connection_id}:{correlation_id}` (redelivery-stable).
   - goal reached: `goal.reached:{goal_id}` (once per goal, ever).
   - month closed: reuse `event.source_key` (`budget.month_closed:{account_id}:{year}:{month}`).
7. [x] `app/workers/notification_consumer.py`: one `ConsumerBase` subclass, queue
   `notification_service.events`, bound to routing keys
   `["bank.sync.completed", "goal.updated", "budget.month_closed"]`; `handle()` parses by
   `event_type`, validates the matching contract model (invalid → `PoisonMessageError`),
   dispatches to the service. Goal path: **ignore unless** `status == completed`. Benign
   duplicate (unique `source_key` `IntegrityError`) → log INFO + ACK (goal-service pattern).
   `python -m app.workers.notification_consumer` entrypoint.

### D. REST read/write API (inbound)  ✅ done 2026-07-20
8. [x] Routes in `main.py` under `/api/v1/notifications`,
   JWT via `finans-tracker-auth` (`user_id` from token, per fase2 decision):
   - `GET /` — list (newest first, `?unread=true`, pagination); excludes dismissed.
   - `GET /unread-count` — `{count}` for the badge.
   - `POST /{id}/read`, `POST /read-all`, `DELETE /{id}` (dismiss) — all user-scoped
     (ownership: `WHERE user_id = <jwt>`), 404 if not owned. CORS + domain-exception→HTTP
     mapping (`execute_with_logging` wrapper per house style).

### E. Frontend feed (additive)
9. [ ] `src/config/serviceUrls.js` + `.env.example`: add
   `NOTIFICATION_SERVICE_URL` (`http://localhost:8008/api/v1`).
10. [ ] `src/api/notifications.jsx`: client (`fetchNotifications`, `fetchUnreadCount`,
    `markRead`, `markAllRead`, `dismiss`) on `apiClient`.
11. [ ] `src/hooks/useNotificationFeed.jsx` (**distinct name** from the toast
    `useNotifications`): TanStack Query list + unread-count with `refetchInterval` ~45s;
    mutations invalidate both keys.
12. [ ] Bell component in `components/Navigation.jsx`: icon + unread badge, dropdown list
    (relative time, read/unread style), "markér alle læst", click → mark-read. Empty state.

### F. Infra & wiring
13. [ ] `docker-compose.yml`: `postgres-notifications` (new volume + port e.g. 5439),
    `notification-service` (API, 8008, healthcheck, migrations on boot per repo convention),
    `notification-consumer` (`command` worker). Env: DATABASE_URL, RABBITMQ_URL, JWT_SECRET,
    ACCOUNT_SERVICE_URL, INTERNAL_API_KEY, CORS_ORIGINS. `depends_on` postgres+rabbitmq
    (+account-service for the consumer). Compare env.py/config/Dockerfile against
    account-service/goal-service (CLAUDE.md extraction gotcha) before first up.
14. [ ] CI (P2-14 pattern): add `notification-service` to the test matrix; add its dir to
    root `Makefile` `PY_SERVICE_DIRS`.

### G. Verification
15. [ ] **Unit** (`make -C services/notification-service test`): message-builders (Danish
    strings, edge cases — 0 imported, errors>0, surplus formatting, singular/plural);
    goal status-flip filter (updated-but-not-completed ⇒ no notification); dispatch by
    event_type; poison payloads. No `datetime.now()` (freezegun/injected clock).
16. [ ] **Integration** (testcontainers): repo idempotency (same `source_key` twice ⇒ one
    row, IntegrityError swallowed); REST endpoints incl. JWT ownership (user B can't read/
    mark user A's rows); consumer **wire-through** test with real UoW (handler-unit ≠
    working path — exam-note lesson, `patterns/idempotent-consumers.md`).
17. [ ] **Live e2e** (full stack `docker compose up`): (a) trigger auto bank-sync
    (scheduler tunable `SYNC_EVERY_HOURS=0` per F1-05 session) → one `BANK_SYNC_COMPLETED`
    notification for the owner; (b) manual "Luk måned" with surplus → one
    `BUDGET_MONTH_CLOSED` (owner resolved via account-service); (c) push a goal to 100% →
    one `GOAL_REACHED`, and a second `goal.updated` after completion produces **no** dup.
    Verify feed list, unread-count badge, mark-read, dismiss, and JWT scoping in the UI.

## Risks & rollback

- **`goal.updated` re-notify storms**: any later edit of a completed goal re-emits
  `goal.updated` with `status=completed`. Mitigated by `source_key = goal.reached:{goal_id}`
  (unique) — notify once ever. Risk if a goal legitimately drops below then hits 100% again:
  accepted (no second "reached") — note in decision if it matters.
- **account-service down when a month closes**: owner unresolvable → let the consumer
  retry/DLQ (do NOT drop). The notification is non-critical, so DLQ + WARNING is acceptable;
  the allocation itself already happened in goal-service independently.
- **Feed polling load**: 45s interval per active client is negligible at this scale; the
  unread-count query is indexed on `(user_id, read_at)`. No websockets in v1.
- **Rollback**: the service is a pure additive consumer + isolated DB + additive frontend.
  Revert = stop `notification-service`/`notification-consumer` containers, delete the queue,
  remove the bell (frontend). No producer or shared-schema change to unwind. Its queue
  binding means unconsumed trigger events simply pile in its own queue/DLQ, harming nothing else.

## Outcome (fill in when done)
_TBD._
