# Adopting finans-tracker-messaging in a service

A mechanical, per-service recipe. The mechanics copy the already-adopted
`finans-tracker-contracts` pattern exactly (reference:
`services/goal-service/pyproject.toml` + `Dockerfile`).

## 1. pyproject.toml

Add the dependency and the path source (path is relative to the
service's own directory):

```toml
[project]
dependencies = [
    # ...existing...
    "finans-tracker-messaging",
]

[tool.uv.sources]
finans-tracker-messaging = { path = "../shared/messaging" }
```

Then, from the service directory:

```bash
uv lock
uv sync
```

The lock records `source = { directory = "../shared/messaging" }`. uv
does **not** content-hash directory sources, so later edits to the
shared package do not invalidate the lockfile — but if the shared
package ever gains a new third-party dependency, re-run `uv lock` in
every adopting service.

Note: the package's runtime deps (`sqlalchemy[asyncio]>=2.0`,
`aio-pika>=9.4.0`) are already direct dependencies of every
outbox-using service, so resolution should not change any pins.

## 2. Dockerfile

Add the COPY **before** the `uv sync --frozen` layer (mirror the
existing contracts line):

```dockerfile
COPY services/shared/messaging /shared/messaging
COPY services/<svc>/pyproject.toml services/<svc>/uv.lock ./
RUN uv sync --frozen --no-dev
```

Why `/shared/messaging` works: `WORKDIR` is `/app`, so the relative
path `../shared/messaging` recorded in pyproject/uv.lock resolves to
`/app/../shared/messaging` = `/shared/messaging` inside the container —
the same relative layout as `services/<svc>/../shared/messaging` on the
host. Do not change WORKDIR or the COPY destination independently.

**Build-context caveat:** `COPY services/shared/...` only works because
docker-compose builds every service with `context: .` (repo root) and
`dockerfile: services/<svc>/Dockerfile`. Building from inside the
service directory (`docker build services/<svc>`) will fail — always
build via compose or with the repo root as context.

If the service runs a separate outbox-worker container from the same
image (see `goal-service-outbox-worker` in docker-compose.yml), no
extra Dockerfile changes are needed — only the API image is built.

## 3. Import swap

| Old (service-local) | New (shared) |
|---|---|
| `app.models.outbox.OutboxEventModel` / outbox tables in `app/models.py` | `class OutboxEventModel(OutboxEventMixin, Base)` — keep a thin local class so Alembic metadata and FKs stay service-owned; `from messaging import OutboxEventMixin` |
| `app.adapters.outbound.postgres_outbox_repository.PostgresOutboxRepository(session)` | `from messaging import OutboxRepository` — `OutboxRepository(session, OutboxEventModel)` (note the extra `model` arg) |
| `app.adapters.outbound.rabbitmq_publisher.RabbitMQPublisher(url)` | `from messaging import RabbitMQPublisher` — `RabbitMQPublisher(rabbitmq_url, exchange_name=EXCHANGE_NAME)`; same `connect()/publish(event)/publish_raw(msg, routing_key)/close()` API |
| `app.workers.outbox_publisher.OutboxPublisherWorker` (per-service variants, see divergences) | `from messaging import OutboxPublisherWorker` — see constructor below |
| hand-rolled consumer boilerplate (`connect_robust`, DLX/DLQ declaration, retry headers) | `from messaging import ConsumerBase, PoisonMessageError` — subclass and implement `async def handle(self, payload, message)` |
| inline `logging.basicConfig(...)` blocks in workers | `from messaging import setup_worker_logging` |
| `datetime.now(timezone.utc).replace(tzinfo=None)` helpers (`_utcnow`, `_utcnow_naive`) | `from messaging import utcnow_naive` (and `utcnow` for aware) |
| magic strings `"pending"` / `"failed"` / `"published"` | `from messaging import OutboxStatus` |
| inline `min(2**attempts * 5, 300)` | `from messaging import compute_backoff` |
| hardcoded `EXCHANGE_NAME = "finans_tracker.events"` | `from messaging import EXCHANGE_NAME` |

Key constructors:

```python
OutboxRepository(session: AsyncSession, model: type[OutboxEventMixin])
# .add(event, aggregate_type, aggregate_id)
# .add_batch(events, aggregate_type, aggregate_id)   # ONE aggregate — see divergence #2
# .fetch_pending(batch_size=10) -> list[OutboxEntry]
# .mark_published(event_id) / .mark_failed(event_id, next_attempt_at)
# .record_failure(entry, *, max_attempts=None) / .purge_published(older_than_days=7)

OutboxPublisherWorker(
    session_factory,               # Callable[[], AsyncSession]
    repository_or_model,           # model class OR Callable[[AsyncSession], repo]
    rabbitmq_url=None,             # or pass publisher=<connected RawPublisher>
    exchange_name=EXCHANGE_NAME,
    poll_interval=2.0, batch_size=20,
    max_attempts=None,             # None = legacy retry-forever
    commit_per_entry=True,         # False = legacy batch-commit-once
    purge_published_after_days=None, purge_interval=3600.0,
    error_backoff=5.0, publisher=None,
)
# .run_forever() / .close()

ConsumerBase(
    rabbitmq_url, queue_name, routing_keys,   # str or sequence of str
    exchange_name=EXCHANGE_NAME, max_retries=3,
    prefetch_count=1, deduplicator=None,      # InboxDeduplicator protocol
)
# .run() / .stop(); override handle(payload, message); raise PoisonMessageError → DLQ
```

Hexagonal note: services that define an `IOutboxRepository` /
`IEventPublisher` port (transaction-, goal-, categorization-service
etc.) should keep the port and either (a) have the shared classes
satisfy it structurally, or (b) keep a thin adapter that delegates to
`OutboxRepository`. Do not import `messaging` from the domain layer —
it is infrastructure; pytest-archon boundaries still apply.

## 4. Delete after adoption

Typical local copies to remove (names vary slightly per service):

- `app/workers/outbox_publisher.py` → replaced by a ~15-line
  `__main__` shim that instantiates `OutboxPublisherWorker` (keep the
  module path so the compose `command: ["python", "-m",
  "app.workers.outbox_publisher"]` keeps working, or update compose).
- `app/adapters/outbound/postgres_outbox_repository.py` (or
  `app/adapters/outbound/outbox_repository.py` in account-service)
- `app/adapters/outbound/rabbitmq_publisher.py`
- `app/models/outbox.py` full column definitions → shrink to
  `class OutboxEventModel(OutboxEventMixin, Base): pass` (or the outbox
  table section of `app/models.py`)
- local `_utcnow` / `_utcnow_naive` helpers and
  `logging.basicConfig` blocks in the deleted modules
- the corresponding unit tests of the deleted copies (the shared
  package has its own 44-test suite); keep service-level tests that
  exercise the service's own handlers/shims

Do **not** delete Alembic migrations that created `outbox_events` —
history must stay replayable. The shared mixin's columns match the
existing table exactly (plus an index `ix_outbox_pending_poll` that new
services get; existing services may add it in a follow-up migration,
it is an optimization, not a requirement).

## 5. Divergence warnings (found by sampling, 2026-07-14)

1. **account-service worker is raw SQL, not ORM**
   (`services/account-service/app/workers/outbox_publisher.py`, 175
   lines): uses `text()` queries and builds its **own async engine**
   from `DATABASE_URL` because the main API uses a sync psycopg2
   engine. When adopting, keep the engine/session-factory creation in
   the shim (`create_async_engine` + `sessionmaker`) and pass it as
   `session_factory`; the service has an ORM `OutboxEventModel`
   (`app/models/outbox.py`) that matches the mixin columns and can be
   passed as `repository_or_model`. Its repo lives at
   `app/adapters/outbound/outbox_repository.py` (non-standard name).

2. **transaction-service `add_batch` has a different signature**
   (`services/transaction-service/app/adapters/outbound/postgres_outbox_repository.py`):
   local `add_batch(entries: list[tuple[BaseEvent, str, str]])` takes
   per-entry `(event, aggregate_type, aggregate_id)` tuples; shared
   `add_batch(events, aggregate_type, aggregate_id)` assumes ONE
   aggregate for the whole batch. Callers batching across aggregates
   (CSV bulk-import paths) must loop or keep a thin adapter — do not
   blindly swap. The local repo also returns the service's own
   `app.domain.entities.OutboxEntry`; the shared repo returns
   `messaging.OutboxEntry` (same fields, minus `published_at`). Update
   the port's type hints or map at the adapter boundary.

3. **goal-service consumer retry bug**: the legacy goal-service
   consumer republishes failed messages to the **topic exchange**,
   re-delivering the event to every bound consumer.
   `ConsumerBase` republishes to its own queue via the default exchange
   (the fixed account-service variant). Adopting fixes the bug — this
   is a deliberate behavior change, do not "preserve" the old routing.

4. **Existing queues lack DLQ arguments**: `ConsumerBase` declares the
   main queue with `x-dead-letter-exchange`/`x-dead-letter-routing-key`.
   RabbitMQ rejects re-declaration of an existing queue with different
   arguments (`PRECONDITION_FAILED`). One-time deploy step per queue:
   stop the consumer, drain, delete the queue
   (`rabbitmqadmin delete queue name=<queue>`), start the new consumer
   (it re-declares and re-binds; events published while the queue is
   absent are lost — do it inside a quiet window or bind a temporary
   catch-all queue first).

5. **Worker crash semantics change (deliberate)**: legacy workers
   crashed on any DB/broker error and relied on container restart
   (`restart: on-failure`). The shared worker logs and retries. Keep
   the compose restart policy anyway; alerting that keyed on
   restart-count should key on the `"Outbox batch failed"` log line
   instead.

## 6. Verification checklist

- [ ] `uv lock && uv sync` in the service succeeds; lockfile diff shows
      only the new `finans-tracker-messaging` entry
- [ ] Service test suite green (`uv run pytest`)
- [ ] `uv run ruff check .` clean
- [ ] `docker compose build <svc>` succeeds (repo-root context)
- [ ] `docker compose up <svc> <svc>-outbox-worker` — worker logs
      `Outbox publisher started`, a domain write produces a
      `Published <event_type>` line, and the consumer side receives it
      (unit-tested handler != working event path — verify live)
- [ ] Outbox row transitions `pending → published` in the service DB
- [ ] For consumers: `<queue>.dlq` exists and a poison message lands in
      it instead of crash-looping
