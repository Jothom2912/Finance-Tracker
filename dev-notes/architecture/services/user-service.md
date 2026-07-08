---
title: user-service + shared libs
updated: 2026-07-07
source: architecture audit 2026-07-07
---

# user-service (port 8001) + services/shared

Auth bounded context: registration, login, JWT issuing. Sole token issuer in the system.

## Structure (hexagonal — the cleanest exemplar in the repo)

- **Inbound**: `app/adapters/inbound/rest_api.py` — `/api/v1/users`: `register`, `login`, `/me` (JWT), `/{user_id}` (internal, `X-Internal-API-Key`).
- **Application**: `app/application/service.py` (`UserService`), DTOs in `dto.py`, ports in `application/ports/` (`IUserRepository`, `IOutboxRepository`, `IEventPublisher`, `IUnitOfWork`).
- **Domain**: frozen dataclasses `User`, `UserWithCredentials` (credential-leak guard), `OutboxEntry`.
- **Outbound**: Postgres repos, `rabbitmq_publisher.py`, async SQLAlchemy `unit_of_work.py`.
- **Entry points**: `app/main.py` (API, runs `alembic upgrade head` at container start — Dockerfile:26) and `app/workers/outbox_publisher.py` (separate container `user-outbox-worker`).
- **DB**: `users` (unique idx on username/email) + `outbox_events` (status, attempts, next_attempt_at; poll index `ix_outbox_pending_poll`).
- **JWT**: `app/auth.py` — bcrypt rounds=12, HS256 via python-jose; claims `sub`, `user_id`, `username`, `email`, `exp`.

## Write + event flow (transactional outbox — reference implementation)

1. `POST /register` → UoW: uniqueness checks → insert user → insert `UserCreatedEvent` outbox row → single commit (atomic; no dual-write).
2. Outbox worker polls every 2s: `SELECT … WHERE status IN ('pending','failed') AND next_attempt_at <= now ORDER BY created_at LIMIT 20 FOR UPDATE SKIP LOCKED` → publish persistent messages to topic exchange `finans_tracker.events`, routing key = `event_type` → mark published/failed (backoff `min(2^attempts*5, 300)s`) → one commit per batch. At-least-once; SKIP LOCKED allows multiple workers.

## services/shared — how it's consumed

- `shared/contracts`: real hatchling package, consumed as **uv path dependency** (`finans-tracker-contracts = { path = "../shared/contracts" }`) and COPY'd into Docker images at `/shared/contracts`. Genuinely shared, tested (428 lines of tests), transport-agnostic. README event table is stale (missing bank/goal/saga/SubCategory events).
- `shared/auth/jwt_utils.py`: **dead code** — no pyproject, zero importers, different JWT lib (PyJWT vs python-jose), incompatible claims. Every service instead carries its own diverged copy of `app/auth.py` (3+ variants).

## Known strengths

Correct outbox UoW; horizontally scalable worker (SKIP LOCKED); poll index matches predicate; modern typing throughout; contracts package is the proven mechanism for sharing code.

## Open problems

See [findings/2026-07-07-architecture-audit.md](../../findings/2026-07-07-architecture-audit.md) — headline items: sync bcrypt blocks the event loop (HIGH), shared HS256 secret lets any service mint tokens (HIGH), 8 copy-pasted outbox workers (MEDIUM), register check-then-insert race → 500 (MEDIUM), no outbox dead-letter/purge (MEDIUM).
