---
title: notification-service hardening — CI, sync-trigger, polish
date: 2026-07-25
status: open            # open | in-progress | done | superseded
backlog-items: [P2-21, P3-17, P3-18]
related:
  - plans/2026-07-20-f101-notification-service-mvp.md
  - plans/2026-07-20-f203-mid-month-budget-alerts.md
  - plans/2026-07-17-f105-scheduled-bank-sync.md
  - findings/2026-07-25-k8s-manifest-drift.md
  - findings/2026-07-25-worker-migration-ordering.md
  - architecture/services/notification-service.md
---

# notification-service hardening — CI, sync-trigger, polish

## Goal

Close the defects found in the 2026-07-25 review of notification-service (F1-01 + F2-03).
Three outcomes, in order of severity:

1. `uv run ruff format --check .` exits 0 in `services/notification-service` — the CI job
   for this service currently **fails** on committed code.
2. The nightly bank-sync (F1-05) stops producing an empty notification per connection per
   night. `BankSyncCompletedEvent` gains a `trigger` field so consumers can distinguish a
   scheduled sweep from a user pressing the button.
3. The low-severity polish list is cleared: connection reuse in the account adapter, honest
   auth-failure classification, a dismissed-guard on the write path, stale docstrings, dead
   compose stub, and the two missing test cases.

Done when: CI green for notification-service *and* banking-service, `make test-e2e` green,
and a live scheduler tick against a bank with no new transactions produces **zero** rows in
`notifications` while a manual sync against the same bank produces one.

## Context

Full review of the shipped service on 2026-07-25 (60/60 tests green, `ruff check` clean,
hexagonal boundaries respected, idempotency correctly pushed into the schema). The design
holds up; what follows are gaps, not rewrites.

Two review findings were **downgraded after verification** and are deliberately not in this
plan:

- *"migrations only run in the API container"* — this is the repo convention, not a
  notification-service deviation. 8 of 9 services put `alembic upgrade head` in the
  Dockerfile `CMD` and no alembic Job/init-container exists anywhere in `k8s/`. The
  consumer-starts-before-migration window is systemic and self-heals via restart →
  [finding](../findings/2026-07-25-worker-migration-ordering.md), P3-17.
- *"notification-service is missing from k8s"* — true, but it is 1 of 5 features that have
  drifted out of `k8s/`; scoping it to notification alone would be arbitrary →
  [finding](../findings/2026-07-25-k8s-manifest-drift.md), P2-21.

`bank.sync.completed` has exactly **one** consumer (notification-service), so the contract
change carries no fan-out risk.

## Non-goals

- **No behaviour change to the four existing triggers.** `goal.updated`, `goal.reached`,
  `budget.month_closed` and `budget.line_threshold_crossed` keep their current
  fire-conditions, `source_key`s and Danish message text verbatim. Only the *bank-sync*
  trigger changes, and only for the scheduled-and-quiet case.
- **No k8s manifests.** Deferred whole to P2-21 (deliberate scope decision, 2026-07-25).
- **No email delivery.** `IEmailPort`/`LogEmailAdapter` stay no-op. Real SMTP stays blocked
  on a notification-preferences decision → P3-18.
- **No retention/purge job.** Also P3-18.
- **No change to the saga.** The `trigger` rides the existing P3-14 claim row, so
  saga-service, the command/reply envelope and the saga step definitions are untouched.
- **No change to idempotency semantics.** `source_key` formats stay byte-identical, so
  already-persisted rows keep deduping against new events.

## Steps

One commit per numbered step (per convention: commit per logical phase, clean rollback).

### 1. [ ] `style(notification): ruff format` — unblock CI

- `make -C services/notification-service format`
- Touches 4 committed files: `app/application/service.py`, `app/domain/messages.py`,
  `tests/unit/test_messages.py`, `tests/unit/test_service.py`.
- Pure whitespace/wrapping. Verify with `git diff --stat` that no logic moved.
- **Do this first and alone** — it is the only step that unblocks the pipeline, and mixing
  it with logic changes makes the rest of the diff unreadable.

### 2. [ ] `feat(contracts): trigger on BankSyncCompletedEvent`

`services/shared/contracts/contracts/events/bank.py`:

```python
class SyncTrigger(str, Enum):
    MANUAL = "manual"
    SCHEDULED = "scheduled"

class BankSyncCompletedEvent(BaseEvent):
    ...
    trigger: SyncTrigger = SyncTrigger.MANUAL
```

`event_version` stays **1**: the field is additive with a default, so old payloads sitting
in an outbox or queue at deploy time still validate. Default is `MANUAL` on purpose — it
errs toward notifying, which is the safe direction for a field that decides whether a user
hears about something.

### 3. [ ] `feat(banking): carry sync trigger on the P3-14 claim`

The claim row is the carrier — it already lives for exactly the saga's lifetime and is
already validated against `saga_id` at completion time. Files:

- `migrations/versions/0XX_add_sync_trigger.py` — `sync_trigger VARCHAR(16) NULL` on
  `bank_connections`, mirroring the P3-14 migration that added `sync_saga_id`/`sync_started_at`.
- `app/domain/entities.py:27` — `sync_trigger: Optional[str] = None` on `BankConnection`.
- `app/adapters/outbound/postgres_bank_connection_repository.py:105` `try_claim_sync(...)`
  and `:130` `steal_sync_claim(...)` — new `trigger` param written in `.values(...)`.
- `app/application/service.py:227` `start_sync_saga(..., trigger: SyncTrigger)` — threads
  it to the claim.
- `app/adapters/inbound/bank_api.py:229` → `trigger=SyncTrigger.MANUAL`.
- `app/workers/sync_scheduler.py:87` → `trigger=SyncTrigger.SCHEDULED`.
- `app/workers/saga_command_consumer.py:~228` — read `conn.sync_trigger` **before** the
  claim-clearing block below it, pass into `BankSyncCompletedEvent(trigger=...)`, fall back
  to `MANUAL` when `NULL` (rows predating the migration).

**Known imprecision, accepted:** if a manual sync *steals* an in-flight scheduled claim
(P3-14 steal path), the old saga's reply reads the new claim's trigger and its event is
labelled `manual`. Worst case is one extra notification — the safe direction. Fixing it
properly means versioning the claim per saga, which is not worth it for a cosmetic label.
Document in the banking architecture doc; do not chase.

### 4. [ ] `feat(notification): suppress quiet scheduled syncs`

- New pure predicate in `app/domain/` (extend `messages.py` or add `rules.py`):
  `should_notify_bank_sync(*, trigger, new_imported, errors) -> bool` — false iff
  `trigger is SCHEDULED and new_imported == 0 and errors == 0`.
- `app/application/service.py:57` `handle_bank_sync_completed` — early-return
  `HandleResult(status="ignored_quiet_sync")` when the predicate is false, before building
  content or touching the repo.
- Extend the `HandleResult.status` docstring comment at `:41`.
- Tests: quiet+scheduled → ignored; quiet+manual → created; scheduled+imports → created;
  scheduled+errors-only → created.

Keeping the rule as a pure function (not an `if` inside the handler) is the house pattern —
it is the part with real edge cases, so it belongs where it can be tested without a UoW.

### 5. [ ] `refactor(notification): reuse httpx client, classify auth failures`

`app/adapters/outbound/account_adapter.py`:

- Hold one `httpx.AsyncClient` for the adapter's lifetime instead of constructing one per
  event (`:25`). The adapter is already long-lived on the consumer (`notification_consumer.py:61`).
  Add an `aclose()` and call it from the consumer's shutdown path.
- Split the catch-all at `:37`: `401/403` → new `AccountOwnerAuthError` (domain exception,
  logged at ERROR, re-raised so it still DLQs) rather than `AccountOwnerUnavailable`. A
  wrong `INTERNAL_API_KEY` must not read as an account-service outage.

### 6. [ ] `fix(notification): dismissed rows are not writable`

`app/adapters/outbound/postgres_notification_repository.py:83,108` — add
`dismissed_at.is_(None)` to the `mark_read` and `dismiss` predicates, so a dismissed
notification 404s instead of returning 204. Today the feed and the write path disagree
about what is gone. `mark_all_read` (`:96`) already filters correctly.

### 7. [ ] `test(notification): close the two coverage gaps`

- `tests/unit/test_consumer.py` — the `IntegrityError` → ACK race path
  (`notification_consumer.py:75`) is currently unexercised; the fake raises it but no test
  drives it through `handle`.
- New `tests/unit/test_account_adapter.py` — HTTP mapping via
  `httpx.MockTransport`: 200 → user_id, 404 → `AccountNotFound`, 500 →
  `AccountOwnerUnavailable`, 401 → `AccountOwnerAuthError`, `RequestError` →
  `AccountOwnerUnavailable`. This adapter is the only place a live dependency is
  interpreted and it has zero tests today.

### 8. [ ] `chore: docstrings, dead compose stub, hollow package`

- `app/workers/notification_consumer.py:1` — "three F1 trigger events" → five routing keys.
- `app/adapters/outbound/account_adapter.py:3-5` — owner-resolution now serves three
  handlers, not just `budget.month_closed`.
- `docker-compose.yml:898-904` — delete the commented-out `# notification-service:` stub;
  the real definition is at `:1035`.
- `app/adapters/inbound/__init__.py` — empty package while the HTTP adapter lives in the
  app root (`main.py`, `auth.py`, `dependencies.py`). Delete the package (cheap, honest)
  rather than moving the API (churn, no behaviour gain). The layout should not claim a
  boundary it does not have.
- Update `architecture/services/notification-service.md`: the bank-sync trigger row gains
  its fire-condition, and note the new `ignored_quiet_sync` status.

### 9. [ ] Verification

```bash
make -C services/notification-service check    # format-check + lint  → must exit 0 (step 1)
make -C services/notification-service test     # 60 existing + new cases
make -C services/banking-service test          # claim/scheduler/API regression
make -C services/shared/contracts test         # additive-field compat
make test-e2e                                  # incl. the F2-03 threshold path
```

Live flow (the part tests cannot prove — cf. the standing exam note that a unit-tested
handler is not a working event path):

1. `docker compose up -d` and confirm `notification-consumer` binds all five routing keys.
2. Manual sync on a connection with nothing new → **one** notification
   ("ingen nye transaktioner"), i.e. the user still gets a receipt for their own click.
3. Force a `banking-sync-scheduler` tick over the same connection → **zero** new rows in
   `notifications`; consumer logs `status=ignored_quiet_sync`.
4. Seed one new transaction, tick the scheduler again → **one** notification.
5. Re-drive one existing trigger (e.g. `budget.month_closed`) to prove step 4's refactor did
   not disturb the owner-resolution path.

## Risks & rollback

| Risk | Detection | Rollback |
|---|---|---|
| Step 3's migration runs against a `bank_connections` table under load | Column is nullable with no default backfill → non-blocking `ADD COLUMN` on PG16 | `alembic downgrade -1` |
| In-flight events published pre-deploy lack `trigger` | Pydantic default `MANUAL` absorbs them; assert in the contracts test | none needed |
| Rows claimed before the migration have `sync_trigger = NULL` | Explicit `MANUAL` fallback in step 3's read | none needed |
| Step 5's shared client leaks connections or is used after close | `httpx` raises on a closed client; consumer restarts | revert step 5 alone (isolated commit) |
| Suppression is too aggressive and hides a real sync | Step 4 tests cover errors-only and imports-only; live step 4 proves the positive case | revert step 4 alone; contract field stays harmless |

Every step is an independent commit and steps 4–8 are individually revertible without
touching the others. Step 3 is the only one with a migration.

## Outcome (fill in when done)

_Not started._
