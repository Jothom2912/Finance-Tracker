# Account Service Extraction — Migration Plan

**Date**: 2026-05-08
**Status**: In progress (Phase 1)
**Authors**: Johan + AI assistant

## Context

Account management lives in the monolith (MySQL). A dedicated
`account-service` (Postgres) is ready but not deployed. This document
records the architecture decisions, phased migration plan, and
constraints for a safe cutover.

**Environment**: Local development, 2 users, one with important data.

**Reference pattern**: `user-service` uses transactional outbox with
async SQLAlchemy. Account-service uses sync SQLAlchemy — outbox inserts
happen in the same sync `Session.commit()`, publisher worker runs as a
separate async process.

## Architecture Decisions

### 1. Read-replica via events (not HTTP adapter)

MySQL `Account` table becomes read-only from monolith's side. It stays
in sync via `account.created` / `account.updated` events published by
account-service's outbox.

**Why not HTTP adapter?** `MySQLAccountResolver` sits on the hot path of
every authenticated request (banking, budgets, analytics). Making it an
HTTP call would:

- Add network roundtrip latency to every request
- Make account-service a SPOF for the entire monolith
- Require circuit breakers, retries, timeouts on the hot path

Read-replica keeps auth checks local, fast, and always available.
Account-service can be down without breaking the monolith.

### 2. Outbox pattern for event publishing

Domain writes and outbox inserts happen in a single database transaction
(same `Session`, same `commit()`). This eliminates the dual-write
problem. A separate async publisher worker polls the outbox table and
publishes to RabbitMQ.

### 3. Idempotency via partial unique index

Default account creation must be idempotent against RabbitMQ
re-delivery. A partial unique index guarantees the invariant at the
database level:

```sql
CREATE UNIQUE INDEX one_default_per_user
  ON "Account" ("User_idUser")
  WHERE name = 'Default Account';
```

The consumer uses a fast-path check (skip if user already has accounts)
combined with `ON CONFLICT` handling. The database catches the race
condition that the consumer check cannot.

### 4. Events carry full state

`AccountUpdatedEvent` includes all fields (not deltas). This makes the
sync consumer self-healing — a missed event is corrected by the next
one. No ordering guarantees required beyond eventual consistency.

### 5. No AccountDeletedEvent (YAGNI)

Account-service has no DELETE endpoint today. The repository has a
`delete()` method but it is unexposed via HTTP. When/if DELETE is added,
the event and sync handler are added in the same commit.

## Phases

### Phase 1 — Infrastructure and Data Migration

1. Fix port conflict: move ai-service host port 8004 to 8007
2. Alembic migration 002: `outbox_events` table + partial unique index
3. Start `postgres-account` + `account-service` (Alembic runs on startup)
4. Run `migrate_from_monolith.py` (dry-run, verify, then real)

**Review point**: verify tables, index, and data counts before proceeding.

### Phase 2 — Event Publishing Infrastructure

1. Add `aio_pika` dependency
2. Sync outbox repository (same `Session` as account repo)
3. Sync Unit of Work (wraps session, exposes repos + outbox)
4. Update `AccountService` to write outbox events after create/update
5. Add `AccountUpdatedEvent` to shared contracts
6. Outbox publisher worker (async, `asyncpg`, polls + publishes)
7. Add `account-service-outbox-publisher` to docker-compose

**Review point**: verify event flow end-to-end (update account, see
event in RabbitMQ management UI).

### Phase 3 — MySQL Read-Replica Sync

1. `AccountSyncConsumer` in monolith (listens `account.created`,
   `account.updated`; upserts into MySQL)
2. Add to docker-compose
3. Test: create account via account-service API, verify MySQL reflects it

**Review point**: MySQL is a live replica. Confirm before cutting writes.

### Phase 4 — Frontend Cutover and Route Removal

1. Add `ACCOUNT_SERVICE_URL` to frontend, update `accounts.jsx`
2. Remove `account_router` and `account_group_router` from monolith
3. End-to-end test: frontend CRUD, ownership checks, transaction creation

**Review point**: write path fully cut over.

### Phase 5 — Account Creation Consumer Cutover

1. New consumer in account-service (listens `user.created`)
2. Worker entry point + docker-compose service
3. Start new consumer, stop old `account-creation-consumer`
4. Delete old queue after draining
5. Update root Makefile

**Final review**: full end-to-end (create user, default account in
Postgres, synced to MySQL, frontend shows it, ownership works).

## Constraints

- Do NOT delete MySQL Account data until final review passes
- Do NOT drop monolith's Account table — it remains as read-replica
- Outbox publisher must be running before any account writes
- AccountSyncConsumer must be running before frontend cutover
- All consumers must be idempotent (upsert on PK, log on conflict)

## Connection String Convention

| Container | Driver | DATABASE_URL |
|-----------|--------|--------------|
| account-service (API) | psycopg2 | `postgresql+psycopg2://...` |
| account-service-consumer | psycopg2 | `postgresql+psycopg2://...` |
| account-service-outbox-publisher | asyncpg | `postgresql+asyncpg://...` |

Each container gets one driver, one URL. No runtime string substitution.

## Exchange and Routing

- Exchange: `finans_tracker.events` (topic, durable)
- Routing keys: `account.created`, `account.updated`
- New queues: `account_service.account_creation` (user.created),
  `monolith.account_sync` (account.*)

## Out of Scope

- API gateway
- Async migration of account-service HTTP layer
- Removing MySQL Account table
- AccountDeletedEvent
