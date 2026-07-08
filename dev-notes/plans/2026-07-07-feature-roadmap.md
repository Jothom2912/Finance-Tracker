---
title: Feature roadmap — sequencing & build sketches
date: 2026-07-07
status: open
backlog-items: [F1-01..F3-06]
related: [../backlog/FEATURES.md, ../backlog/BACKLOG.md, 2026-07-07-refactoring-roadmap.md]
---

# Feature roadmap

## Goal

Turn the feature backlog ([FEATURES.md](../backlog/FEATURES.md)) into an executable sequence that interleaves with the refactoring roadmap instead of fighting it. Every feature follows the house patterns: hexagonal service layout, transactional outbox, contracts in `services/shared/contracts`, AsyncAPI entry per new event, tests per service + e2e for cross-service flows.

## Sequencing (interleaved with refactor phases)

```
Refactor Phase 2 (P2-01/02/03 shared libs)          ← do FIRST: every F1 feature consumes events
   │
   ├─► Wave 1: F1-01 notifications ∥ F1-02+F1-03 rules & feedback (∥ = parallelizable)
   │            F1-04 goal allocation completion (independent, can start anytime)
   ├─► Wave 2: F1-05 scheduled sync (needs P2-08)  ∥  F2-01 recurring detection
   ├─► Wave 3: F2-02 forecast → F2-03 alerts → F2-06 chat intents
   │            F2-04 semantic search (needs P3-04) ∥ F2-05 report export
   └─► Wave 4 (bets, pick by appetite): F3-01 household (after group ownership),
                F3-02 net worth (after F1-05), F3-03 multi-currency (after P2-09)
```

Rule of thumb: **one feature wave per refactor phase completed** — features keep proving the refactors, refactors keep features cheap.

## Build sketches (top items)

### F1-01 Notification service MVP
1. Flesh out `services/notification-service` from the stub using the post-P2-01 shared consumer/outbox libs (first consumer of the new package — deliberate).
2. DB: `notifications` (user_id, type, payload, read_at, created_at) + `processed_events` inbox; own Postgres (compose + k8s, ports 8008/5441).
3. Consumers: `budget.month_closed`, goal events, saga bank-sync completion. Contracts already exist; add a `notification.created` contract + AsyncAPI entries.
4. API: `GET /api/v1/notifications` (JWT), `POST /{id}/read`. Frontend: bell + feed via TanStack Query; reuse NotificationContext for toasts.
5. Email channel behind a port (log-adapter in dev, SMTP later). Verify: e2e — close a month → notification row + feed shows it.

### F1-02 + F1-03 User rules & feedback loop
1. Prereq P2-06 (engine reads rules DB; consumer uses shared provider).
2. Rules CRUD on categorization-service (`/api/v1/rules`, JWT, user-scoped; user rules rank above seed rules — priority column exists).
3. Feedback: on manual category change, transaction-service emits `transaction.category_corrected` (new contract); categorization consumer upserts merchant mapping (`is_user_confirmed=true` — finally uses the dead flag) so next import auto-applies.
4. Frontend: "opret regel fra denne transaktion" shortcut in the transaction edit modal; simple rules admin page.
5. Verify: correct a transaction → import a similar CSV row → auto-categorized correctly; rules editable without service restart (TTL reload from P2-06).

### F1-04 Goal allocation completion (ADR-0003)
Work directly from `docs/followups.md`'s gap list (consumer/publisher/frontend). Frontend: allocation history on GoalPage (`goal_allocation_history` already has the data), "unallocated surplus" card wired to `unallocated_budget_surplus`. Verify: e2e month-close → goal balance + history visible in UI.

### F1-05 Scheduled bank sync
1. Prereqs: P2-08 (consent expiry persisted), P3-14 (deterministic saga correlation id per connection+day — prevents overlap).
2. Scheduler worker in banking-service (post-P2-01 worker base): daily scan of active, non-expired connections → start sync saga each (same code path as the manual button). K8s alternative: KEDA cron ScaledJob (pattern already in repo).
3. Reconsent: connections within 14 days of expiry → `bank.reconsent_needed` event → notification (F1-01) + banner on BankConnectionWidget.
4. Verify: worker triggers saga for due connections exactly once/day (idempotent via correlation id); expired connection → notification, no saga.

### F2-01 Recurring detection & subscriptions
1. Detection job in transaction-service (maintenance worker): group by normalized description + account, flag groups with ≥3 occurrences at ~monthly/weekly cadence and stable amount (±10%). Store `recurring_series` table; link transactions.
2. API `GET /api/v1/recurring` + subscriptions page (monthly cost, next expected date, last amount change).
3. Optional: "confirm as planned transaction" → creates `planned_transactions` row (model exists).
4. Verify: seeded fixture with 3× Netflix rows → detected series with correct cadence/amount.

## Non-goals

- No new bounded contexts beyond notification-service; features live in the services that own the data.
- No feature work that bypasses the outbox/contracts/AsyncAPI conventions "because it's just a small thing".
- F3 items get their own plan files before any code — this document only sequences them.

## Risks & rollback

- Feature creep before Phase 2 lands → every new consumer copies the outbox boilerplate a 9th time. Mitigation: Wave 1 starts only after P2-01 merges.
- Notification fatigue: default to digest-style, per-type opt-out from day one.
- Scheduled sync hitting EB rate limits: per-connection jitter + daily cap.

## Outcome

_(fill in as waves complete)_
