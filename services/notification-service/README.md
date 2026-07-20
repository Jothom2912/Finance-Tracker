# Notification Service

Per-user **in-app notification feed** for the finance tracker. Consumes the auto-events
the F1 chain produces and turns them into notifications the user can see, mark as read,
and dismiss.

Port: **8008** · DB: PostgreSQL (`notifications`) · Hexagonal (domain / ports / adapters).

## Triggers (v1)

| Event (routing key) | Notification | user_id source |
|---------------------|--------------|----------------|
| `bank.sync.completed` | "Banksynkronisering færdig" | on the event |
| `goal.updated` → `status == "completed"` | "Mål nået! 🎉" (once per goal) | on the event |
| `budget.month_closed` | "Måned lukket" (+ surplus) | resolved via account-service `/internal/accounts/{id}/owner` |

`transaction.categorized` is deliberately **not** consumed (too noisy, no value).

## Idempotency

At-least-once delivery. Each notification carries a deterministic `source_key` with a
unique index; duplicates (redelivery, repeated `goal.updated`) collapse onto the same row.
See [dev-notes plan](../../dev-notes/plans/2026-07-20-f101-notification-service-mvp.md).

## Email

Deferred. `IEmailPort` exists with a log/no-op adapter so real SMTP can be wired later
without touching the application layer.

## Processes

- API: `uvicorn app.main:app` (port 8008) — REST feed under `/api/v1/notifications`.
- Consumer: `python -m app.workers.notification_consumer` — one queue bound to the three
  trigger routing keys, DLQ + retry via `finans-tracker-messaging` `ConsumerBase`.

## Development

```
make install-deps   # uv sync --dev
make test           # pytest
make check          # ruff format-check + lint
make migrate        # alembic upgrade head
```
