---
date: 2026-07-17
topic: Scheduler pattern for periodic jobs — in-service worker-loop container, not KEDA cron
status: active
---

# Scheduler pattern: in-service worker-loop container

Needed by F1-07 (scheduled day-7 month-close) and reused by F1-05 (scheduled bank
sync). The F1-04 decision explicitly deferred this choice; it pairs the two features.

## Decision

Periodic jobs run as **long-lived worker containers with an asyncio sleep-loop**, one
per service that owns the job — exactly the shape of the existing outbox-publisher
workers (same image, own `command:`, own compose service). The tick interval is env-
configured; the job itself must be idempotent so tick frequency is a liveness knob,
not a correctness knob.

Rejected alternatives:

- **KEDA cron ScaledJob** — only exists in the k8s demo; docker compose is the primary
  runtime, and a scheduling mechanism that silently doesn't run in the main dev
  environment is how "works in k8s, never ran locally" bugs are born. Can still be
  adopted later per-job in k8s as an *optimization* (scale-to-zero) without changing
  the job code: the loop body is a plain async function.
- **Host cron / compose one-shots** — no home in the current deploy story, no retry
  semantics, adds an orchestration surface outside the repo's patterns.
- **In-API background task (FastAPI lifespan)** — couples job lifecycle to API
  replicas; N replicas = N schedulers, and an API restart silently kills the job.

## Consequences / rules for jobs using this pattern

1. **Idempotency is mandatory** — the loop WILL fire on work that a human (or a crash-
   restart) already did. Guards live in the data layer (e.g. `mark_closed`'s
   `WHERE closed_at IS NULL`, goal-side `source_key` dedup), never in the loop.
2. **Single replica per job** — no distributed locking; the idempotency guards make a
   accidental second replica harmless (one loser logs a no-op), but don't scale these
   workers horizontally on purpose.
3. **A missed tick must be self-healing**: each tick recomputes "what is due now" from
   the DB — never from in-memory state — so downtime is caught up on the next tick.
4. **Clock is injected** into the due-logic (CLAUDE.md: no `datetime.now()` in domain);
   the worker shell is the only place that reads wall-clock time.
5. Trade-off accepted: a container idles 24/7 for a job that fires ~monthly. Cost is
   one sleeping asyncio process (~20 MB); in exchange the job runs in every
   environment compose runs in, with `docker logs` observability and the restart
   policies from P2-16.
