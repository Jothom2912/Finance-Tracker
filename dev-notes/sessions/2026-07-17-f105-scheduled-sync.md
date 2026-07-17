---
date: 2026-07-17
topic: F1-05 shipped — nightly bank-sync scheduler; ADR-0003 chain now fully automatic
---

# F1-05: scheduled bank sync

Plan: [plans/2026-07-17-f105-scheduled-bank-sync.md](../plans/2026-07-17-f105-scheduled-bank-sync.md).
One code commit (`7c113932`) + docs. Fourth item today (P3-16 → F1-07 → P3-14 → F1-05).

## Done

- `BankConnection.is_sync_due(now, every_hours)` — staleness rule (never-synced or
  >24 h), injected clock, naive/aware normalisering.
- Repo sweep `list_active_synced_before(cutoff)`; consent filtering in the worker via
  the entity (distinct logging).
- `app/workers/sync_scheduler.py` (worker-loop pattern, 2nd user after F1-07):
  `run_once` + loop shell; per-connection session + exception isolation; expired
  consent → WARNING skip (v1 reconsent surface); expiring <7 d → WARNING but synced;
  `already_running` → INFO defer. Same `start_sync_saga` use case as the button;
  `bearer_token=None` ⇒ conflicts defer, stale claims recover via claim TTL.
- Compose `banking-sync-scheduler` (EB volumes — client PEM smoke-test at
  construction; wiring identical to API DI). Config: `SYNC_SCHEDULER_INTERVAL_SECONDS`
  3600 / `SYNC_EVERY_HOURS` 24 / `SYNC_CONSENT_WARN_DAYS` 7.
- 52 tests + lint green (8 sweep + 2 entity due-rule tests, mock style).

## Live e2e (real EB-sandbox connection): PASSED

1. `SYNC_EVERY_HOURS=0`, 15 s tick → first tick auto-started a saga; completed,
   `last_synced_at` bumped, P2-09 dedup skipped everything.
2. **P3-14 race proof, opposite direction**: a manual sync was running when the next
   tick fired → scheduler logged `1 already-running` and deferred. No duplicate saga.
3. Claim cleared after final saga; prod-config container (24 h) up: `0 candidates`.

## Learned / gotchas

- Test-fejl at kende: en sync `_run`-helper der returnerer en uawaited coroutine fra
  en `with patch(...)`-blok — patchen er væk når corotinen kører. Helper skal være
  async og awaite inde i blokken.
- `docker compose run --rm -d -e X=…` er mønstret for engangs-kørsel af en scheduler
  med test-tunables uden at røre compose-filen (også brugt i F1-07).

## Milestone

**ADR-0003-kæden er nu fuldautomatisk**: nightly sync (F1-05) → day-7 close (F1-07) →
surplus → goal-allokering (F1-04) — nul brugerdisciplin. F1-sporet mangler kun F1-01
(notifications — nu med rigtige auto-events at notificere om) og F1-06 (ML-tier).

## Open ends

- Reconsent-UI-banner + auto-sync-notifikationer → F1-01.
- k8s manifests stadig uden de to schedulers (bevidst, samlet ved næste k8s-arbejde).
