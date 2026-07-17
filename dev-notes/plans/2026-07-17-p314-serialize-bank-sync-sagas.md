---
title: P3-14 — Serialize bank-sync sagas per connection (in-flight claim)
date: 2026-07-17
status: done
backlog-items: [P3-14]
related:
  - ../patterns/saga-orchestration.md
  - ../decisions/2026-07-16-p209-dedup-semantics.md
  - ../plans/2026-07-17-f107-scheduled-month-close.md
---

# P3-14 — Serialize bank-sync sagas per connection

## Goal

Two concurrent sync requests for the same bank connection produce ONE saga: the second
request gets the already-running saga's id back (`already_running: true`) instead of
spawning a racing duplicate. Done when: double-request returns the same `saga_id`; a
completed/failed saga releases the claim so the next sync starts fresh; and a crashed
saga can't block syncs forever (TTL fallback). Prerequisite for F1-05 (scheduled sync
must not race a manual button press).

## Context

Audit M8: `start_sync_saga` mints a fresh `saga_id` per request (`service.py:245`) —
double-click ⇒ two concurrent sagas racing the import dedup. P2-09's
`(account_id, external_id)` dedup makes duplicate *imports* mostly harmless, but the
duplicate *sagas* still both fetch from Enable Banking (slow, rate-limited), bloat
saga-context rows, and can interleave compensation in ways nobody has tested. F1-05
(scheduled sync) would make the race an every-night event instead of a double-click
curiosity — hence P3-14 is its prerequisite.

**Design: in-flight claim on `bank_connections`** (banking-service owns serialization;
saga-service untouched):

- New nullable columns `sync_saga_id` + `sync_started_at` on `bank_connections`.
- `start_sync_saga` claims atomically — conditional UPDATE wins or loses, no lock:
  claim + outbox `saga.bank_sync.start` event commit in ONE transaction.
- On claim conflict: check the claimed saga's status via saga-service's status API
  (forwarding the **caller's JWT** — the status API is owner-checked (P1-04), and the
  caller owns the connection, hence the saga). Terminal (`completed`/`failed`/
  `timed_out`) → steal the claim (conditional UPDATE scoped to the old saga_id — only
  one stealer wins) and start fresh; active → return the existing saga_id.
- saga-service unreachable during the check → **fail active** (return existing claim)
  while the claim is younger than `SYNC_CLAIM_TTL_SECONDS` (default 600 = 2× the saga
  timeout-worker's 300 s idle limit); older → steal. The TTL is the backstop that makes
  a crashed/never-resolved saga unable to block syncs forever.
- `mark_sync_complete` (success path) clears the claim in the same transaction that
  sets `last_synced_at`. Failure paths release via the status-check/TTL above — banking
  never hears about saga failure (no failure event exists; adding one is out of scope).

Rejected alternatives: deterministic `correlation_id = f"bank_sync:{connection_id}"`
(the audit's literal suggestion) breaks on retry-after-failure — `saga_instances.
correlation_id` is unique across ALL rows, so a terminal saga would block every future
sync. Dedup inside saga-service's start-consumer leaves the second caller polling a
saga_id that never comes into existence.

## Non-goals

- No saga-service changes (no failure-notification event, no internal status endpoint,
  no schema change there).
- No frontend change required: response stays 202 with `saga_id`; `already_running` is
  additive (UI may later use it for an "allerede i gang"-toast — not now).
- No change to saga semantics, import dedup (P2-09), or compensation.
- Scheduled sync itself is F1-05, not this.

## Steps

1. [ ] **Migration 003** (banking): `bank_connections` + `sync_saga_id VARCHAR(36) NULL`,
   `sync_started_at TIMESTAMP NULL`. Simple add-columns; real downgrade.
2. [ ] **Repo + model** — `models/bank_connection.py`, `postgres_bank_connection_repository.py`
   + `ports/outbound.py`: map new fields onto the `BankConnection` entity;
   `try_claim_sync(connection_id, saga_id, now, ttl) -> bool` (UPDATE … WHERE id=:id
   AND (sync_started_at IS NULL OR sync_started_at < :now - :ttl), rowcount==1);
   `steal_sync_claim(connection_id, old_saga_id, new_saga_id, now) -> bool` (WHERE
   sync_saga_id = :old — one winner); `clear_sync_claim(connection_id, saga_id)`
   (WHERE sync_saga_id = :saga_id — release only own claim).
3. [ ] **Saga-status port** — `ISagaStatusPort.get_status(saga_id, bearer_token) ->
   str | None` (None = unreachable/unknown); HTTP adapter against
   `SAGA_SERVICE_URL` `GET /api/v1/sagas/{id}` with forwarded Authorization header,
   short timeout (2 s). Config: `SAGA_SERVICE_URL`, `SYNC_CLAIM_TTL_SECONDS` (600).
4. [ ] **Service** — `start_sync_saga` gains the claim flow above and returns
   `(saga_id, already_running)`; claim UPDATE + outbox add + commit in one UoW
   transaction. Clock stays injected (`self._clock()` exists). API
   (`bank_api.py` sync route): response model gains `already_running: bool`, still 202.
5. [ ] **Consumer** — `saga_command_consumer._handle_mark_sync_complete`: clear claim
   (scoped to the saga_id being completed) alongside `last_synced_at`.
6. [ ] **Tests** (banking suite): repo claim/steal/clear semantics incl. TTL boundary
   (sqlite or existing test DB pattern — match the house style in banking tests);
   service: fresh claim → new saga + event; conflict + active status → existing id,
   NO event; conflict + terminal status → steal + new event; conflict + status port
   None + fresh claim → existing id; + stale claim → steal. Consumer: complete clears
   claim only when saga_id matches.
7. [ ] **Verification** — `make -C services/banking-service test` + lint. Live e2e
   (dev stack has a working EB-sandbox connection from P2-09/loose-ends sessions):
   two rapid `POST /connections/{id}/sync` → same saga_id, second says
   `already_running`; poll saga to terminal; third sync → NEW saga_id (claim released
   by mark_sync_complete or steal-on-terminal); psql: claim columns cleared/rotated.
8. [ ] **Docs close-out** — BACKLOG P3-14 done; FEATURES F1-05 "Needs first" → all ✓;
   arch doc (banking section: claim columns + flow line) + saga-pattern doc gotcha
   line updated; session log; plan Outcome.

## Risks & rollback

- **Claim leaks block syncs**: bounded by TTL (600 s) + steal-on-terminal. Worst case
  (saga-service down AND saga dead) a user waits 10 min — acceptable vs. racing sagas.
- **Status-check adds an HTTP hop**: only on the conflict path (rare), 2 s timeout,
  fail-active. No hop on the happy path.
- **Forwarded JWT expiry**: the token just authenticated the sync request, so it is
  valid now; a 401 from saga-service is treated as unreachable (fail-active) — never a
  crash.
- **Rollback**: revert code + downgrade migration; behavior returns to
  fresh-saga-per-request (the current state).

## Outcome (fill in when done)

Shipped same day in one code commit (`f1d36d22`) + docs. One scope deviation from
step 6: no DB-level repo tests — banking-service has no sqlite/testcontainers test
setup (models use the Postgres UUID dialect, house style is mock-based unit tests +
fake-service API tests), so the claim/steal/clear SQL semantics were verified live
instead, and the flow logic got 6 service-level unit tests + 2 consumer tests
(42 total green + lint).

Live e2e against the real EB-sandbox connection: PASSED — two concurrent sync POSTs
returned the SAME saga_id (one `started`, one `already_running`); after the saga
completed, the claim columns were cleared by `mark_sync_complete` and a third sync got
a fresh saga_id (claim rotated during the run, cleared after). Migration 003 applied
cleanly at container start.

Local-runnability gotcha (recorded in session log): banking-service has no venv/uv
project — tests run via `uv run --python 3.11 --with-requirements` (psycopg2 filtered
out, needs pg_config on macOS) with a lazy asyncpg DATABASE_URL.

F1-05's prerequisites are now all met. Session log:
[sessions/2026-07-17-p314-sync-claim.md](../sessions/2026-07-17-p314-sync-claim.md).
