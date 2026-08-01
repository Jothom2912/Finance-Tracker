---
title: P2-21 + P3-17 Kubernetes parity and explicit migration ordering
date: 2026-08-01
status: done
backlog: [P2-21, P3-17]
related:
  - ../findings/2026-07-25-k8s-manifest-drift.md
  - ../findings/2026-07-25-worker-migration-ordering.md
  - ../decisions/2026-08-01-explicit-migration-phases.md
---

# P2-21 + P3-17 Kubernetes parity and explicit migration ordering

## Goal

Make the checked-in Kubernetes deployment represent every product workload that Compose runs,
and make schema migration an explicit prerequisite for both APIs and workers in Compose and
Kubernetes. Completion means the missing notification API/consumer/database and four schedulers
or consumers run from Kubernetes, a failed migration prevents dependent processes from starting,
and an automated parity check fails when a future deployable Compose workload has no Kustomize
resource or explicit allowlist entry.

## Context

The current facts still match
[the P2-21 finding](../findings/2026-07-25-k8s-manifest-drift.md): Compose has six workloads and
one Postgres instance absent from `k8s/` — `notification-service`, `notification-consumer`,
`postgres-notifications`, `banking-sync-scheduler`, `budget-month-close-scheduler`,
`budget-alert-scheduler`, and `analytics-embedding-consumer`. The consequence is a Kubernetes
system without the notification feed or the automatic ADR-0003 chain.

The existing Kubernetes workers also have no schema-ordering barrier. Eight Dockerfiles migrate
as part of API startup, `account-service` migrates in its lifespan, and worker command overrides
skip both paths. Adding the missing workers without P3-17 would reproduce that race. The proposed
[deployment-phase decision](../decisions/2026-08-01-explicit-migration-phases.md) therefore treats
the two backlog items as one rollout-shaped change.

## Non-goals

- Do not change notification, scheduler, consumer, outbox, or domain behavior.
- Do not change migration contents or downgrade databases.
- Do not introduce Helm, a GitOps controller, SOPS, new production credentials, NetworkPolicy,
  resource tuning, or worker liveness probes; those remain P2-15/P3-11/P3-27 concerns.
- Do not solve Compose image building or stale worker images; P3-40 already owns that invariant.
- Do not make Kubernetes the production source of truth beyond the workloads already represented
  by Compose; local-only tooling and infrastructure must be explicitly allowlisted in parity
  checks rather than blindly manifested.

## Steps

1. [x] **Lock the inventory and parity contract** — extend `scripts/compose_check.py` (and its
   focused tests, creating `tests/unit/test_compose_check.py` only if no suitable test module
   exists) with a stdlib-only rule that parses Compose service names and Kustomize resource
   targets. Classify infrastructure and intentionally local-only services in a named allowlist
   with reasons. Prove the negative control first: the current repository must report exactly the
   known seven P2-21 omissions, and removing one existing worker resource must make the rule red.
2. [x] **Separate migrations from API processes in Compose** — add one-shot migration services
   for the nine Alembic-backed schemas in `docker-compose.yml`; point APIs and every DB-backed
   worker at the matching service with `condition: service_completed_successfully`. Remove
   `alembic upgrade head &&` from the eight Dockerfile `CMD`s and remove `account-service`'s
   `_run_migrations()`/lifespan migration path while preserving its normal startup and logging.
   Give migration services no published ports and reuse the owning service image and exact
   database URL.
3. [x] **Prove Compose ordering, including failure** — extend the compose structural check to
   require one migration owner per Alembic-backed service and completed-success dependencies from
   each API/worker. Run a disposable-schema treatment where migrations complete before the API and
   workers become healthy, then a negative control with an intentionally invalid migration command
   and verify the dependent containers remain unstarted rather than crash-looping. Restore the
   valid command before continuing.
4. [x] **Add the missing Kubernetes resources** — create
   `k8s/apps/notification-service.yaml`, `k8s/workers/notification-consumer.yaml`,
   `k8s/workers/banking-sync-scheduler.yaml`,
   `k8s/workers/budget-month-close-scheduler.yaml`,
   `k8s/workers/budget-alert-scheduler.yaml`,
   `k8s/workers/analytics-embedding-consumer.yaml`, and
   `k8s/infra/postgres-notifications.yaml`, following the current API, worker, and Postgres shapes.
   Add `DATABASE_URL_NOTIFICATION` and `DATABASE_URL_NOTIFICATION_SYNC` to
   `k8s/secrets.yaml.example` and the local ignored secret template used for verification; add only
   settings actually consumed by these processes to `k8s/configmap.yaml`.
5. [x] **Introduce a staged Kubernetes migration phase** — add one Job per Alembic-backed schema
   under `k8s/migrations/`, using the owning application image and database secret, plus bounded
   retry/backoff. Split Kustomize entry points so bootstrap/infrastructure, migrations, and
   workloads can each render independently while the root still renders the complete inventory
   for validation. Update `scripts/k8s-up.sh` to apply infrastructure, wait for all Postgres
   Services/Deployments, recreate and apply migration Jobs, fail on any unsuccessful Job with its
   logs, and only then apply APIs/workers. Document the staged script as the supported rollout path.
6. [x] **Wire inventory and configuration** — add every new resource and migration Job to its
   owning `kustomization.yaml`; update image-building/loading scripts if notification-service is
   absent; ensure selectors, image names, module commands, ports, database hosts, secret-key names,
   and health probes match the current Compose definitions and application configuration rather
   than the dated line references in the findings.
7. [x] **Static verification and mutation controls** — run `make compose-check`,
   `make compose-state-check` where applicable, `kubectl kustomize` for every staged entry point,
   and `make compose-check` after temporarily removing (a) one new Kustomize resource and (b) one
   migration dependency. Both mutations must fail for the intended reason; restore them and rerun
   green. Run `make compose-check` after all Dockerfile/Compose changes as required by repository
   guidance.
8. [x] **Live Kubernetes verification** — on a clean disposable namespace/database, run
   `scripts/k8s-up.sh`; verify all migration Jobs complete before dependent pods are created, all
   APIs become ready, and every worker/scheduler remains Running without migration-related
   restarts. Inspect logs rather than relying on pod phase alone. Exercise notification health and
   one event-to-notification flow, then verify the three schedulers and embedding consumer loaded
   their intended modules. Re-run the deployment against the migrated databases to prove
   idempotency.
9. [x] **Close knowledge and findings** — after successful live verification, mark both findings
   resolved, accept the proposed migration decision, set P2-21/P3-17 done, fill this plan's Outcome,
   and update `STATUS.md`. Run `make notes-check` last.

## Risks & rollback

- **A missing dependency starts code against an old schema.** The structural rule detects absent
  Compose dependencies; the clean-namespace Kubernetes run detects staged-rollout gaps.
- **A completed Kubernetes Job is accidentally reused.** `scripts/k8s-up.sh` must recreate Jobs
  each rollout and verify their fresh completion; job age/log inspection is part of live evidence.
- **The parity rule confuses infrastructure with application workloads.** Keep exceptions in one
  reviewed allowlist with a reason, and mutation-test both a required workload and an allowlisted
  service.
- **Removing migration code changes API startup behavior.** Container startup tests cover imports,
  health and logs after a fresh migration and against an already-current schema; account-service's
  access logging is checked explicitly because its migration path previously reconfigured logging.
- **Schema succeeds but a new manifest has wrong configuration.** Render checks cannot prove
  runtime imports or connections, so the clean-cluster run and per-process logs are mandatory.
- **Rollback:** revert manifests, Compose dependencies, Dockerfile commands and orchestration
  together. Do not run Alembic downgrade automatically. If a new migration has already applied,
  keep backward-compatible application images or ship a forward corrective migration before
  restoring traffic.

## Outcome

Shipped and live-verified 2026-08-01. Compose completed all nine one-shot migrations before all
33 gated API/worker processes, passed `make compose-state-check` with 62 containers, and handled a
real `bank.sync.completed` notification. The parity/migration gate covers 53 required Compose
resources among 89 rendered Kubernetes names and has focused mutation tests.

The first Kubernetes treatment exposed two defects before workloads: transaction and notification
Jobs received sync URLs even though importing their models constructs async engines, and nine
simultaneous migration pods caused OOM retries in the shared 7.8 GiB Docker Desktop VM. The Jobs
now receive async URLs (their Alembic env converts them), and `k8s-up.sh` applies and awaits the nine
Jobs sequentially. A full Compose stack competing with Kubernetes still exhausted the local VM;
stopping Compose, restarting Docker Desktop, and recreating only the disposable `finance-tracker`
namespace separated that known P3-46 capacity limit from application behavior.

The clean treatment then completed all nine fresh-database Jobs before creating any application
Deployment. Every Deployment became Available; every long-running pod was Running with zero
restarts; the six new workloads' logs showed the intended API, consumer and scheduler modules; and
notification `/health` returned 200. A synthetic `bank.sync.completed` message traversed RabbitMQ
and produced exactly one row with the expected source key in notification Postgres. Re-running the
entire staged script recreated all nine Jobs with new pods, completed against already-current
schemas, left every workload unchanged at zero restarts, and preserved the notification row.

Final verification: `make compose-check`, all three `kubectl kustomize` entry points,
`tests/unit/test_compose_check.py` (3 passed), account-service tests (44 passed), `git diff --check`,
and `make notes-check`. Compose containers and volumes remain preserved but stopped; the verified
Kubernetes namespace remains running.
