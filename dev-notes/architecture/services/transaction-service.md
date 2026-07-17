---
title: transaction-service
updated: 2026-07-17
source: architecture audit 2026-07-07; F1-03 update 2026-07-17
---

# transaction-service (port 8002)

Largest service: transaction CRUD, CSV import, bulk import, planned transactions, saga participant, taxonomy read-copies. Hexagonal, mostly clean; `TransactionService` is a 625-line god-ish application service.

## Structure

- **Domain**: frozen dataclasses `Transaction`, `PlannedTransaction`, `Category`, `SubCategory`, `OutboxEntry`.
- **Application**: `app/application/service.py` (`TransactionService`), DTOs, ports, `csv_parsers/` (Protocol + `internal`, `nordea`, `danske_bank` parsers + registry).
- **Inbound**: `rest_api.py` — `/api/v1/transactions` (POST/GET list cached 60s/GET/PUT/DELETE/{id}, `/import-csv`, `/bulk` max 500) + `/api/v1/planned-transactions`.
- **Outbound**: Postgres repos (transaction, planned, category + subcategory read-copies, outbox), async UoW, `rabbitmq_publisher.py`, `categorization_client.py` (sync HTTP → categorization-service, 500ms timeout, graceful degrade to None — no port interface, duck-typed).
- **Workers (4 containers)**: `outbox_publisher` (poll 2s, batch 20, SKIP LOCKED), `categorized_consumer` (applies `transaction.categorized`, skips `tier="manual"`, inbox dedup via `processed_events`), `taxonomy_sync_consumer` (maintains `categories`/`subcategories` read copies per ADR-003), `saga_command_consumer` (`saga.cmd.bulk_import_transactions` / `saga.cmd.rollback_import` → `saga.reply.*`).
- **DB**: 10 Alembic migrations; `transactions`, `planned_transactions`, taxonomy read copies, `outbox_events`, `processed_events` (inbox, unique `(message_id, consumer_name)`), positive-amount CHECK.
- **Redis**: only fastapi-cache2 on the list endpoint; URL hardcoded in `main.py:29`.

## Data flows

- **Manual create**: POST → optional sync categorization HTTP (500ms, caller's category wins) → UoW: denormalize names from local read copies → insert row + `TransactionCreatedEvent` outbox → outbox worker → `transaction.created` → categorization pipeline → `transaction.categorized` → categorized_consumer updates row.
- **Manual correction** *(F1-03, 2026-07-17)*: PUT with category-field change → `categorization_tier="manual"` + second outbox event `TransactionCategoryCorrectedEvent` (`transaction.category_corrected`, skipped when the correction clears the category) → categorization-service's corrected-consumer learns a user rule. See [decisions/2026-07-17-learned-corrections-as-rules.md](../../decisions/2026-07-17-learned-corrections-as-rules.md).
- **CSV import**: whole file into memory → parser registry → per-row `find_duplicate` SELECT (dedup key `(user_id, account_id, date, amount, description)`) → bulk insert + batch outbox in one commit.
- **Saga bulk import**: `saga.cmd.bulk_import_transactions` → `bulk_import` (no sync categorization) → reply with `imported_ids`. Compensation `rollback_import` = per-id **hard** delete, failures swallowed, always replies success (⚠).
- **Taxonomy sync**: categorization-service owns taxonomy (ADR-003); full-state `category.*`/`subcategory.*` events upserted into local read copies.

## Open problems

See [findings/2026-07-07-architecture-audit.md](../../findings/2026-07-07-architecture-audit.md). Headliners: saga rollback swallows failures + hard-deletes (HIGH), unbounded list queries with broken filter/pagination combination (HIGH), N+1 dedup SELECTs in imports with no composite index and no in-batch/concurrent-import guard (HIGH), list cache keyed on object repr → useless + stale-on-write (MEDIUM), consumer retries re-broadcast to the whole platform via topic exchange (MEDIUM), prefetch=1 + inline sleep = head-of-line blocking (MEDIUM), `/bulk` reachable with plain user JWT and no account-ownership validation (LOW/security).

## Strengths

Outbox+inbox idempotency, taxonomy read-copy design (ADR-003), graceful-degrade sync categorization, positive-amount CHECK, tombstoned migration hygiene.
