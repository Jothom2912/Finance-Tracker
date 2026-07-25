---
title: Rebuilding a service does not rebuild its workers (per-worker build blocks)
date: 2026-07-25
severity: MEDIUM
area: infrastructure
status: open
resolved-by: null
---

# Rebuilding a service does not rebuild its workers

**Where**: `docker-compose.yml` — every worker/consumer/scheduler that carries its own
`build:` block pointing at the *same* Dockerfile as its API service. At least:
`banking-saga-command-consumer`, `banking-sync-scheduler`, `banking-outbox-worker`,
`notification-consumer`, `saga-reply-consumer`, `saga-start-consumer`, `saga-outbox-worker`,
`saga-timeout-worker`, `transaction-saga-command-consumer`, and the budget/analytics
schedulers and consumers.

**Defect**: because each of these declares `build:` rather than reusing the API service's
image, Compose builds and tags a **separate image per compose service** — 
`finance-tracker-banking-saga-command-consumer`, `finance-tracker-notification-consumer`, …
So:

```bash
docker compose build banking-service notification-service saga-service
docker compose up -d --force-recreate banking-saga-command-consumer notification-consumer
```

looks like it deploys new code and does not. The `build` step rebuilt three images; the
workers' own images were untouched, and `--force-recreate` faithfully recreated the container
from the **stale** image. `docker compose ps` says `running`, the startup banner looks right,
and nothing anywhere reports a version.

**How it actually surfaced**: during the F1-05 quiet-sweep live verification
([plan](../plans/2026-07-25-notification-service-hardening.md) step 9). The API container had
new code and wrote `bank_connections.sync_trigger` on the claim; the saga-command consumer was
running an image from 2026-07-20 that had never heard of the column. The observable result was
a *passing* scenario — a notification appeared for a quiet manual sync — for entirely the
wrong reason: the old consumer never set `trigger`, so the event fell back to the Pydantic
default `MANUAL`, which notifies. A mixed-version system produced exactly the output the new
code was supposed to produce.

The tell was a leftover `sync_trigger='manual'` on a row whose `sync_saga_id` was already
NULL — impossible under the new code, which clears all three together.

**Why this matters beyond local dev**: it is the same failure shape as the existing
"`alembic upgrade head` exit-coded 0 but created no tables" rule — a step that reports success
while the thing you cared about did not happen. Here it is worse in one respect: the system
keeps working, in a half-migrated code state, and any verification run against it is
worthless without telling you so.

**Detection that works**: grep the *running container* for a symbol the change introduced.

```bash
docker compose exec -T banking-saga-command-consumer grep -c own_claim app/workers/saga_command_consumer.py
# 0 → stale image, stop and rebuild; >0 → new code is live
```

**Fixes, in order of preference**:

1. Give the workers `image:` + `depends_on` on the API service's build instead of their own
   `build:` block, so one build produces one image per service and all its workers share it.
   Compose supports this directly (`image: finance-tracker-banking-service`).
2. Failing that, always `docker compose build` with **no service filter** before a live
   verification, and accept the longer build.
3. Add a `/version` or startup log line carrying the git SHA (build arg), so a stale worker is
   visible in `docker compose logs` instead of requiring a `grep` into the container.

Option 1 also cuts build time and image storage substantially — the banking Dockerfile is
currently built four times to produce four byte-identical images.

**Related**: [worker-migration-ordering](2026-07-25-worker-migration-ordering.md) (same
"workers are second-class citizens of the compose file" root), P3-17.
