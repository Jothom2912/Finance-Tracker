---
title: Database migrations run as an explicit deployment phase
date: 2026-08-01
status: accepted
backlog: [P2-21, P3-17]
supersedes: null
promoted-to-adr: null
---

# Database migrations run as an explicit deployment phase

## Decision

Make migrations a deployment phase owned by the deployment definitions, not a side effect of
starting an API process. Compose will use one-shot migration services and
`service_completed_successfully`; Kubernetes will use per-service Jobs applied and awaited by
`scripts/k8s-up.sh` before API and worker resources are applied.

The supported Kubernetes deployment path becomes the staged script. Kustomizations remain
independently renderable for static validation, but a single unordered `kubectl apply -k k8s/`
is not a supported rollout command because Kubernetes does not impose dependency order between
a Job and a Deployment in the same apply.

## Context

[P3-17's finding](../findings/2026-07-25-worker-migration-ordering.md) shows that eight API
Dockerfiles run `alembic upgrade head` in `CMD`, while workers replace that command and rely on
the API having migrated first. Compose hides the dependency through API healthchecks; Kubernetes
does not. [P2-21](../findings/2026-07-25-k8s-manifest-drift.md) is about to add five more
database-backed workloads, so copying the current manifest shape would enlarge the race.

An explicit phase also removes `account-service`'s exceptional in-process migration, which is
the reason it needs the logging repair described in
[P3-58](../findings/2026-07-31-account-service-log-silenced-by-alembic.md).

## Alternatives considered

- Keep migrations in API startup and make every worker wait for API readiness — rejected because
  it gives the API an unrelated privileged role, couples independently scalable workloads, and
  still has no native Kubernetes ordering guarantee.
- Put `alembic upgrade head` in every pod's init container — rejected because several replicas
  can execute the same DDL concurrently; making that safe would require a new cross-service
  advisory-lock convention and migration-runner code.
- Apply migration Jobs and Deployments together, then let pods crash-loop until the Jobs finish —
  rejected because it preserves the exact misleading failure mode P3-17 is meant to remove.
- Use Helm hooks or an external GitOps controller — rejected because the repository deploys with
  Kustomize today, and adopting a second deployment owner is disproportionate to this change.

## Consequences

APIs and workers start only after their schema reaches head, and failure is reported at the
migration phase instead of as an application crash loop. Docker images become process-neutral:
their default command starts the API and the deployment layer decides when migrations run.

The cost is that Kubernetes rollout ordering lives in `scripts/k8s-up.sh`; direct unordered
apply is no longer a supported deployment path. Migration Jobs must be recreated on each rollout
because completed Job specs do not rerun when reapplied. Database downgrades remain deliberately
unsupported: rollback means stop the rollout, restore the previous application image, and use a
forward corrective migration when schema compatibility requires it.
