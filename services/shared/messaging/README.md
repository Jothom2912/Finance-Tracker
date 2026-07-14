# finans-tracker-messaging

Shared messaging infrastructure: transactional outbox (model mixin,
repository, publisher worker), RabbitMQ topic-exchange publisher, and a
consumer base class with DLQ + header-based retry. Consolidates the
per-service copies of `app/workers/outbox_publisher.py`,
`app/adapters/outbound/postgres_outbox_repository.py`,
`app/adapters/outbound/rabbitmq_publisher.py` and the consumer
boilerplate found across the services.

SQL predicates, backoff formula (`min(2**attempts * 5, 300)` s), message
shape (persistent, `content_type='application/json'`, routing key =
`event_type`) and exchange name (`finans_tracker.events`) match the
existing copies exactly, so migration is drop-in. See `MIGRATION.md` for
the per-service adoption recipe.

## What this package does NOT do

It has **no dependency on `finans-tracker-contracts`**. Events are
accepted via the structural `SerializableEvent` Protocol (anything with
`event_type`, `correlation_id` and `to_json()` — which
`contracts.base.BaseEvent` satisfies). Keep it that way: contracts stays
transport-agnostic, messaging stays schema-agnostic.

## Install

```toml
dependencies = [
    "finans-tracker-messaging",
]

[tool.uv.sources]
finans-tracker-messaging = { path = "../shared/messaging" }
```

## Usage

### Outbox write-side (inside the domain transaction)

```python
from messaging import OutboxEventMixin, OutboxRepository
from app.database import Base

class OutboxEventModel(OutboxEventMixin, Base):
    pass

repo = OutboxRepository(session, OutboxEventModel)
await repo.add(event, aggregate_type="goal", aggregate_id=str(goal.id))
# same transaction as the domain write — commit together (outbox pattern)
```

### Publisher worker (standalone process)

```python
import asyncio
from messaging import OutboxPublisherWorker, setup_worker_logging
from app.database import async_session_factory
from app.models import OutboxEventModel
from app.config import settings

setup_worker_logging(__name__)
worker = OutboxPublisherWorker(
    session_factory=async_session_factory,
    repository_or_model=OutboxEventModel,
    rabbitmq_url=settings.RABBITMQ_URL,
)
asyncio.run(worker.run_forever())
```

Improvements over the legacy copies (all opt-out/opt-in — defaults are
safe):

- The loop survives transient DB/broker errors (logged + retried)
  instead of crashing the process.
- `commit_per_entry=True` (default): each entry is published and
  committed in its own transaction, so a crash mid-batch never loses
  publish marks. `commit_per_entry=False` restores legacy
  batch-commit-once.
- `max_attempts=N`: exhausted entries are parked in the terminal
  `'dead'` status instead of retrying forever (legacy behaviour:
  `max_attempts=None`).
- `purge_published_after_days=N`: hourly housekeeping of old published
  rows.

### Direct publisher (no outbox)

```python
from messaging import RabbitMQPublisher

publisher = RabbitMQPublisher(settings.RABBITMQ_URL)
await publisher.connect()
await publisher.publish(event)   # SerializableEvent
```

### Consumer with DLQ + retry

```python
from messaging import ConsumerBase, PoisonMessageError

class BudgetMonthClosedConsumer(ConsumerBase):
    async def handle(self, payload, message):
        try:
            event = BudgetMonthClosedEvent.model_validate(payload)
        except ValidationError as exc:
            raise PoisonMessageError(str(exc)) from exc
        ...

consumer = BudgetMonthClosedConsumer(
    rabbitmq_url=settings.RABBITMQ_URL,
    queue_name="goal_service.budget_month_closed",
    routing_keys="budget.month_closed",
    deduplicator=my_processed_events_inbox,  # optional InboxDeduplicator
)
await consumer.run()
```

Topology: durable topic exchange, direct DLX `<exchange>.dlx`, DLQ
`<queue>.dlq`. Failed messages are republished to the consumer's **own**
queue via the default exchange with an incremented `x-retry-count`
header (max 3 by default), then dead-lettered. Poison messages
(unparseable JSON, non-object payloads, `PoisonMessageError`) go
straight to the DLQ.

**Deploy caveat:** if the queue already exists *without* the
dead-letter arguments, RabbitMQ rejects the declaration
(`PRECONDITION_FAILED`). The old queue must be drained and deleted once
— see `MIGRATION.md`.

## Architecture

```text
messaging/
├── outbox.py    # OutboxEventMixin, OutboxRepository, OutboxEntry, OutboxStatus, compute_backoff
├── worker.py    # OutboxPublisherWorker
├── rabbitmq.py  # RabbitMQPublisher, SerializableEvent, EXCHANGE_NAME
├── consumer.py  # ConsumerBase, InboxDeduplicator, PoisonMessageError
├── time.py      # utcnow, utcnow_naive
└── logging.py   # setup_worker_logging
```

## Design decisions

- **Naive UTC timestamps** (`utcnow_naive`): every service stores outbox
  timestamps in `TIMESTAMP WITHOUT TIME ZONE` columns filled with UTC
  wall-clock time; the helpers centralise that convention rather than
  change it.
- **`SKIP LOCKED` polling**: multiple worker instances never
  double-publish. SQLite (tests) silently drops the FOR UPDATE clause.
- **Retry via own queue, not topic exchange**: republishing a failed
  message to the topic exchange would re-deliver it to every bound
  consumer (a real bug in one legacy copy). The base class republishes
  to its own queue via the default exchange.
- **At-least-once delivery**: consumers must be idempotent. The
  `InboxDeduplicator` hook (`processed_events`-style) gives a fast-path
  skip; strict once-only effects belong in the handler's own DB
  transaction.

## Testing

```bash
cd services/shared/messaging
uv sync --extra dev
uv run pytest
```

44 tests + 1 non-strict xfail (`test_survives_transient_errors_and_recovers`
— a test-harness race on the shared in-memory SQLite connection, not a
worker defect; tracked as dev-notes P2-01).
