---
title: notification-service
updated: 2026-07-25
source: F1-01 (plans/2026-07-20-f101-notification-service-mvp.md)
related:
  - plans/2026-07-25-notification-service-hardening.md
---

# notification-service (8008)

Per-user **in-app notification feed**. Terminal consumer of five trigger events →
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
  `goal.reached`, `budget.month_closed`, `budget.line_threshold_crossed` on the topic
  exchange; `ConsumerBase` (DLQ + retry).

No outbox / no producer — it emits nothing.

## Triggers → notifications

| Routing key | Fires when | user_id | source_key (idempotency) |
|-------------|-----------|---------|--------------------------|
| `bank.sync.completed` | **unless the sync was scheduled *and* quiet** — suppressed iff `trigger=scheduled AND new_imported=0 AND errors=0` (`domain/rules.py:should_notify_bank_sync`) | on event | `bank.sync.completed:{connection_id}:{correlation_id}` |
| `goal.updated` | `current_amount >= target_amount` (>0) — manual goal edit | on event | `goal.reached:{goal_id}` (once per goal) |
| `goal.reached` | automatic surplus allocation completes a goal (F1-08) | **resolved** via account-service | `goal.reached:{goal_id}` (shared with `goal.updated`) |
| `budget.month_closed` | always | **resolved** via account-service `/api/v1/internal/accounts/{id}/owner` | `event.source_key` = `budget.month_closed:{account_id}:{year}:{month}` |
| `budget.line_threshold_crossed` | a budget line is at/over a threshold (80%/100%) in the running period — emitted by budget-service's alert scheduler (F2-03) | **resolved** via account-service (same as month_closed) | `event.source_key` = `budget.line_threshold_crossed:{account_id}:{year}:{month}:{category_id}:{threshold}` (threshold in key ⇒ 80/100 fire once each) |

`HandleResult.status` values: `created` · `duplicate` · `ignored_not_reached` (goal below
target) · `ignored_quiet_sync` (the suppression above) · `account_not_found`.

**Why bank-sync needs a fire-condition at all:** F1-05's nightly sweep completes for every
connection whether or not anything moved, and `source_key` carries `correlation_id`, so a
"0 new transactions" notification could not dedupe against last night's — it wrote a fresh
empty row per connection per night. The `trigger` field distinguishing a scheduled sweep
from a user's button press rides the P3-14 claim row from banking-service; a manual sync
still notifies on zero imports, because there the user asked and deserves a receipt.

Goal-reached has **two producers** that converge on one `source_key`:
- **manual** edits → `goal.updated` (carries user_id); detected **by amount, not stored
  status** (the stored status is active/paused, never computed "completed").
- **automatic** surplus allocation → `goal.reached` (F1-08; carries account_id, owner
  resolved here so goal-service's money path stays decoupled from account-service).

Both write `goal.reached:{goal_id}`, so whichever lands first wins and the other dedupes —
a goal never notifies twice. (Resolved [finding 2026-07-20](../../findings/2026-07-20-goal-reached-not-emitted-on-allocation.md).)

## Storage

Postgres `notifications` (own DB, container `postgres-notifications`, host port 5441): `id`
UUIDv7 PK, `user_id`, `type`, `title`, `body`, `source_key` (**unique** = idempotency
backstop), `read_at`/`dismissed_at` (soft-delete), `created_at`. Index `(user_id,
created_at)`. `sa.Uuid` dialect-agnostic so tests run on sqlite.

## Design notes

- **Idempotency in the schema** (unique `source_key`), not app memory — redelivery and the
  noisy `goal.updated` stream collapse onto one row; consumer ACKs the `IntegrityError`.
- **Asymmetric failure handling** on owner resolution: `AccountNotFound` ⇒ drop
  (ACK, nobody to notify); `AccountOwnerUnavailable` / `AccountOwnerAuthError` ⇒ propagate ⇒
  retry/DLQ (never lose it). 401/403 are split out as `AccountOwnerAuthError` and logged at
  ERROR so a wrong `INTERNAL_API_KEY` does not read as an upstream outage — retrying a
  rejected key never helps.
- **One HTTP pool for the adapter's lifetime**: the account adapter is built once per
  consumer and holds a single `httpx.AsyncClient`, closed from the consumer's shutdown path.
- **"Gone" means gone on every path**: `dismissed_at IS NOT NULL` excludes a row from the
  feed, the unread count, `mark_all_read` *and* both single-row write endpoints — so
  `POST /{id}/read` and a repeat `DELETE /{id}` 404 rather than 204. The cost is that
  dismiss is not idempotent (a double-click 404s); one definition of gone is worth it.
- **Email deferred**: `IEmailPort` + `LogEmailAdapter` (no-op); best-effort, never fails the
  message. Real SMTP is a follow-up.
- Frontend feed = `useNotificationFeed` hook + `NotificationBell` (45s poll). Distinct from
  the transient toast `useNotifications`/`NotificationContext` — unrelated systems.
