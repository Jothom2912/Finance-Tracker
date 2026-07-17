---
title: F1-05 — Scheduled/automatic bank sync (nightly per active connection)
date: 2026-07-17
status: done
backlog-items: [F1-05]
related:
  - ../decisions/2026-07-17-scheduler-pattern-worker-loop.md
  - ../plans/2026-07-17-p314-serialize-bank-sync-sagas.md
  - ../plans/2026-07-17-f107-scheduled-month-close.md
---

# F1-05 — Scheduled bank sync

## Goal

Bank connections sync themselves: a scheduler worker starts a sync saga for every
active connection whose last sync is older than `SYNC_EVERY_HOURS` (24), so the app
stays current without the user pressing anything. Done when: a stale connection is
auto-synced live end-to-end (saga completes, `last_synced_at` bumps), a fresh
connection is NOT re-synced, an expired consent is skipped with a reconsent-warning
log instead of a doomed saga, and the P3-14 claim demonstrably keeps the scheduler
from racing the manual button. This completes the full ADR-0003 chain: **nightly sync
→ day-7 close → surplus → goal** — zero user discipline required.

## Context

- FEATURES F1-05 ("the single biggest UX gap"); all prerequisites now met: P2-08
  (consent expiry persisted + gated), P3-14 (in-flight claim — scheduler cannot race
  the button; a lost race just returns the running saga_id), and the
  [worker-loop scheduler pattern](../decisions/2026-07-17-scheduler-pattern-worker-loop.md)
  with F1-07's month-close worker as reference implementation.
- Staleness-based ("last sync > 24 h ago, checked hourly") rather than a fixed
  clock-hour: self-healing after downtime (rule 3 of the scheduler decision — each
  tick recomputes due-ness from the DB), and it needs no cron parsing. In practice
  syncs settle into a daily rhythm anchored at first-deploy time.
- The scheduler calls the SAME `start_sync_saga` use case as the button: claim,
  consent gate, ownership (each row's own `user_id`), event — nothing forked. It
  passes `bearer_token=None`, so on claim conflict the status check is skipped and it
  fails ACTIVE (defers to the running saga); stale claims are still recovered because
  the TTL lives in `try_claim_sync` itself, not in the status check.

## Non-goals

- No fixed-time cron semantics (03:00-style) — staleness rule only; revisit if a
  bank-hours constraint ever appears.
- No frontend changes required. `expires_at` is ADDED to the connections-list response
  (cheap, additive) so the UI *can* build the reconsent banner later, but the banner
  itself and any notification on auto-sync completion wait for F1-01.
- No change to saga, claim (P3-14), import dedup (P2-09) or consent semantics — the
  scheduler is only a new caller.
- No k8s manifests (same deliberate gap as F1-07).

## Steps

1. [ ] **Due-rule on the entity** — `app/domain/entities.py`:
   `BankConnection.is_sync_due(now, every_hours) -> bool` (True when
   `last_synced_at` is NULL or older than `every_hours`; naive/aware normalised via
   the existing `_as_utc`). Clock injected — the worker shell is the only wall-clock
   reader (scheduler-decision rule 4).
2. [ ] **Repo sweep-query** — `postgres_bank_connection_repository.py` + port:
   `list_active_synced_before(cutoff) -> list[BankConnection]`
   (`status='active' AND (last_synced_at IS NULL OR last_synced_at < :cutoff)`).
   Consent filtering happens in the worker via the entity (distinct logging), not in SQL.
3. [ ] **Worker** — `app/workers/sync_scheduler.py` (shape of F1-07's
   `month_close_scheduler`): testable `run_once(session_factory, now, ...) -> counts`
   + trivial loop shell. Per connection, fresh session/UoW + per-connection exception
   isolation: consent expired → WARNING "reconsent required", skip (counted — this IS
   the v1 reconsent surface); consent expiring within `SYNC_CONSENT_WARN_DAYS` (7) →
   WARNING but still sync; `already_running=True` → INFO (lost race to button/claim —
   fine); unexpected → ERROR, continue. Tick-summary log. Config:
   `SYNC_SCHEDULER_INTERVAL_SECONDS` (3600), `SYNC_EVERY_HOURS` (24),
   `SYNC_CONSENT_WARN_DAYS` (7).
4. [ ] **Compose** — `banking-sync-scheduler`: banking image,
   `command: python -m app.workers.sync_scheduler`, env copied from
   `banking-saga-command-consumer` + the three tunables, `volumes:
   *enable-banking-volumes` (the EB client's PEM smoke-test runs at construction —
   the scheduler builds the same BankingService wiring as the API even though
   `start_sync_saga` never calls EB).
5. [ ] **Tests** (banking suite, mock style): entity due-rule (NULL, fresh, stale,
   naive-datetime from DB); `run_once` with patched repo + fake service factory —
   due → `start_sync_saga` called with the ROW's user_id and `bearer_token=None`;
   not-due filtered; expired consent skipped + counted; warn-window logged;
   already_running counted, no error; one connection's exception doesn't stop the rest.
6. [ ] **Verification** — banking tests + lint. Live e2e against the real EB-sandbox
   connection: scheduler container with `SYNC_EVERY_HOURS=0`, 15 s tick → auto-starts
   a saga (log line + claim set) → saga completes, `last_synced_at` bumps, P2-09
   dedup skips all items; while a scheduler-saga runs, press the manual sync →
   `already_running` + same saga_id (the P3-14 proof); then `SYNC_EVERY_HOURS=24` →
   tick reports 0 due. Finally bring up the prod-config container.
7. [ ] **Docs close-out** — FEATURES F1-05 → done (F1 = alle items done undtagen
   F1-01/F1-06); arch docs (banking: new worker; infrastructure: 17 workers);
   session log; plan → done + Outcome.

## Risks & rollback

- **Nightly saga against a dead consent** would burn retries: gated twice (worker
  skips expired via entity; `start_sync_saga` raises `BankConsentExpired` as backstop).
- **Scheduler + button racing**: exactly what P3-14 was built for; the race is
  verified live in step 6, not assumed.
- **EB rate limits**: one saga per connection per 24 h + the P3-14 claim is strictly
  LESS traffic than today's manual clicking; sandbox unaffected.
- **First tick after deploy syncs every stale connection at once**: dev has one
  connection; for a future multi-user deploy the tick is sequential (per-connection
  sessions), which is natural rate-limiting. Noted in the compose comment.
- **Rollback**: stop/remove the compose service — manual sync untouched. Migration-free.

## Outcome (fill in when done)

Shipped same day in one code commit (`7c113932`) + docs; executed as planned, no scope
deviations (52 banking tests + lint green; 8 new sweep tests + 2 entity due-rule tests).

Live e2e against the real EB-sandbox connection: PASSED — with `SYNC_EVERY_HOURS=0`
the first tick auto-started a saga (completed, `last_synced_at` bumped, P2-09 skipped
all duplicates). The P3-14 race proof landed in the OPPOSITE direction of the plan's
script, which is even stronger evidence: a manual sync was running when the next tick
fired, and the scheduler logged `1 already-running` and deferred to it. Claim cleared
after the final saga; prod-config container (24 h) now runs in the stack and reported
`0 candidates` on its first tick.

The `expires_at`-in-connections-list step was NOT needed — dropped during
implementation (the reconsent surface is the scheduler's WARNING logs; the UI banner
remains with F1-01 as planned).

Session log: [sessions/2026-07-17-f105-scheduled-sync.md](../sessions/2026-07-17-f105-scheduled-sync.md).
