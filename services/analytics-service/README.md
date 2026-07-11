# Analytics Service

Elasticsearch-backed denormaliseret read store (CQRS-læsesiden) for
Finans Tracker. Konsumerer events fra alle services og eksponerer
aggregerings-/søge-endpoints, som gateway-servicen læser fra.

## Arkitektur

- **Skriveside**: `app/workers/projection_consumer.py` konsumerer
  `transaction.*`, `account.*`, `category.*`/`subcategory.*` og `goal.*`
  fra RabbitMQ (topic exchange `finans_tracker.events`) og projicerer
  til ES-indices bag aliaser (`transactions`, `accounts`, `taxonomy`,
  `goals`). Idempotens via dokument-`_id` + event-timestamp-guards —
  ingen `processed_events`-tabel (se ADR-004).
- **Læseside**: `GET /api/v1/analytics/*` (JWT-auth) — overview,
  expenses-by-month, cashflow-by-month, comparison, transactions
  (dansk fuldtekstsøgning), top-merchants. Aggregeringer sker i ES.
- Domain-laget (`app/domain/`) ejer de kanoniske regler for
  expense/income-klassifikation og budgetmåneds-perioder.

## Kørsel

```bash
docker compose up -d elasticsearch analytics-service analytics-projection-consumer
```

API på `http://localhost:8012`. Engangs-backfill af historiske data:
`python -m app.tools.backfill` (se fil-docstring).

## Test

```bash
uv run pytest            # unit + integration (testcontainers-ES)
uv run ruff check app tests
uv run mypy
```
