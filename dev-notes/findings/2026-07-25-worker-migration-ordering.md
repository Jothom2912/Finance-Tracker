---
title: Workers depend on the API container to run migrations
date: 2026-07-25
severity: LOW
area: infrastructure
status: open
backlog: [P3-17]
resolved-by: null
---

# Workers depend on the API container to run migrations

**Where**: every service Dockerfile with `alembic upgrade head` in `CMD` — 8 of 9
(`services/{user,transaction,goal,budget,banking,categorization,saga,notification}-service/Dockerfile`)
— combined with the worker containers that override `command:` in `docker-compose.yml`.

**Defect**: Schema migration is a side effect of starting the *API* container. Worker and
consumer containers override `command:` (e.g.
`docker-compose.yml:1063` → `python -m app.workers.notification_consumer`), which discards
the `alembic upgrade head &&` prefix. A worker therefore assumes some other container has
already migrated its database.

In compose this is papered over by explicit ordering — notification-consumer waits on
`notification-service: service_healthy` (`docker-compose.yml:1073-1074`). There is no
equivalent guarantee in k8s, and no alembic Job or init-container exists anywhere under
`k8s/` (`grep -rln alembic k8s/` → no matches).

**Why it matters**: Low, and deliberately rated so. On a cold k8s namespace the worker pods
start before the API pod finishes migrating, crash on the first query against a missing
table, and `CrashLoopBackOff` until the API catches up — then converge. It is noisy, not
lossy: no data is corrupted and no event is dropped (unacked messages redeliver).

The real cost is diagnostic. A crash-looping consumer is an alarming symptom with a benign
cause, and the compose `depends_on: service_healthy` line reads like a startup-ordering
nicety rather than what it actually is — the only thing making the schema exist. Someone
will eventually delete it as redundant.

Note this is also why the coupling looks strange in review: the consumer does not need the
API, it needs the API's *migration side effect*.

**Suggested fix**: Make migration an explicit step rather than an implicit one — a
per-service `Job` (k8s) / one-shot service (compose) running `alembic upgrade head`, with
API and workers alike depending on its completion. That removes the API's privileged role
and lets workers scale independently of it.

Repo-wide by nature: fixing one service in isolation would make it the odd one out, which
is a worse state than consistent debt. Sequence it with P2-21, since both are k8s-manifest
work on the same files. Tracked as P3-17.

Explicitly **not** in
[plans/2026-07-25-notification-service-hardening.md](../plans/2026-07-25-notification-service-hardening.md):
the 2026-07-25 review initially flagged this as a notification-service defect. It is not —
notification-service follows the house convention exactly.
