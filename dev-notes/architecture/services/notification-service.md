---
title: notification-service
updated: 2026-07-20
source: F1-01 (plans/2026-07-20-f101-notification-service-mvp.md)
---

# notification-service (8008)

Per-user **in-app notification feed**. Terminal consumer of three F1 trigger events →
persistent notifications the user reads/dismisses via a bell in the frontend nav. Shipped
F1-01 (2026-07-20). Hexagonal: `domain` (entity, message builders, uuid7) / `application`
(ports + `NotificationService`) / `adapters` (Postgres repo+UoW, log-email, account HTTP).

## Processes

- **API** (`app.main:app`, 8008) — REST feed under `/api/v1/notifications`: list
  (`?unread`, pagination), `/unread-count`, `POST /{id}/read`, `POST /read-all`,
  `DELETE /{id}` (dismiss). JWT via `finans-tracker-auth`; every query owner-scoped
  (`user_id` from token), foreign id ⇒ 404.
- **notification-consumer** (`python -m app.workers.notification_consumer`) — one queue
  `notification_service.events` bound to `bank.sync.completed`, `goal.updated`,
  `budget.month_closed` on the topic exchange; `ConsumerBase` (DLQ + retry).

No outbox / no producer — it emits nothing.

## Triggers → notifications

| Routing key | Fires when | user_id | source_key (idempotency) |
|-------------|-----------|---------|--------------------------|
| `bank.sync.completed` | always | on event | `bank.sync.completed:{connection_id}:{correlation_id}` |
| `goal.updated` | `current_amount >= target_amount` (>0) | on event | `goal.reached:{goal_id}` (once per goal) |
| `budget.month_closed` | always | **resolved** via account-service `/api/v1/internal/accounts/{id}/owner` | `event.source_key` = `budget.month_closed:{account_id}:{year}:{month}` |

Goal detection is **by amount, not stored status** — `goal.updated` carries the stored
status (active/paused), never "completed" (that's computed). See
[finding 2026-07-20](../../findings/2026-07-20-goal-reached-not-emitted-on-allocation.md):
the auto surplus-allocation path emits **no** `goal.updated`, so goal-reached currently
only fires on manual goal edits (follow-up **F1-08**).

## Storage

Postgres `notifications` (own DB, container `postgres-notifications`, host port 5441): `id`
UUIDv7 PK, `user_id`, `type`, `title`, `body`, `source_key` (**unique** = idempotency
backstop), `read_at`/`dismissed_at` (soft-delete), `created_at`. Index `(user_id,
created_at)`. `sa.Uuid` dialect-agnostic so tests run on sqlite.

## Design notes

- **Idempotency in the schema** (unique `source_key`), not app memory — redelivery and the
  noisy `goal.updated` stream collapse onto one row; consumer ACKs the `IntegrityError`.
- **Asymmetric failure handling** on month-close owner resolution: `AccountNotFound` ⇒ drop
  (ACK, nobody to notify); `AccountOwnerUnavailable` ⇒ propagate ⇒ retry/DLQ (never lose it).
- **Email deferred**: `IEmailPort` + `LogEmailAdapter` (no-op); best-effort, never fails the
  message. Real SMTP is a follow-up.
- Frontend feed = `useNotificationFeed` hook + `NotificationBell` (45s poll). Distinct from
  the transient toast `useNotifications`/`NotificationContext` — unrelated systems.
