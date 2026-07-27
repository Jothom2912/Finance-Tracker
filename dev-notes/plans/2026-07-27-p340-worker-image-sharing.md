---
title: P3-40 — workers share their API service's image instead of building their own
date: 2026-07-27
status: done
backlog-items: [P3-40]
related:
  - ../findings/2026-07-25-per-worker-image-staleness.md
  - ../findings/2026-07-25-worker-migration-ordering.md
---

# P3-40 — workers share their API service's image

## Goal

Make `docker compose build <service>` produce **one** image that the service's API container
and all its workers run, so rebuilding a service actually deploys its workers. Done when
`docker images | grep finance-tracker | wc -l` drops from 13 service images + 26 worker images
to 13, and a symbol introduced by a rebuild is greppable inside a worker container that was
never named in the build command.

## Context

[per-worker image staleness](../findings/2026-07-25-per-worker-image-staleness.md): all 26
workers carry their own `build:` block pointing at the same Dockerfile as their API service,
so Compose builds and tags a separate image per compose service. Measured today: **56
`finance-tracker-*` images**, of which 5 are orphans from removed services (`monolith`,
`account-sync-consumer`, `category-sync-consumer`, `transaction-sync-consumer`,
`categorization-category-sync`, all June).

This is a verification defect, not a runtime defect. The system keeps working in a
half-migrated state and *any live test run against it is worthless without saying so* — during
the F1-05 quiet-sweep check a scenario passed for the wrong reason, because the old consumer
never set `trigger` and the Pydantic default `MANUAL` happened to produce the expected output.

**k8s already does the right thing** and is the precedent to copy: every manifest in
`k8s/workers/` references `finance-tracker/<api-service>:local`, one image per service, built
once by `scripts/build-k8s-images.sh`. Compose is the outlier.

## Non-goals

- **No change to what any worker runs.** `command:`, env, `depends_on`, healthchecks,
  restart policies and volumes stay byte-identical; only the image *source* changes.
- **Not P3-17** (workers skip migrations because they override `command:`). Same root
  ("workers are second-class citizens of the compose file"), different failure.
- **Not the git-SHA startup banner** (option 3 in the finding). That makes staleness
  *visible*; this makes it *impossible*. Worth doing later, not needed once the images merge.
- Not touching `k8s/`, which is already correct, nor the 5 orphan images (untracked cruft;
  `docker image prune` is the user's call, not a commit).

## Steps

1. [ ] **Pin the project name.** Add top-level `name: finance-tracker` to `docker-compose.yml`.
   Today the image tags are inferred from the *directory name* — hardcoding
   `image: finance-tracker-x` while the tag is inferred means a clone into a differently-named
   directory silently breaks every worker. One line, and it is what makes step 2 safe.
2. [ ] **Declare the tag on the 10 API services.** Add explicit `image: finance-tracker-<svc>`
   next to the existing `build:` on user, goal, transaction, account, categorization, budget,
   banking, analytics, saga, notification. Same string Compose infers today, so no rebuild —
   but now it is a written contract instead of a default the workers depend on invisibly.
3. [ ] **Swap the 26 workers.** Replace each worker's 3-line `build:` block with
   `image: finance-tracker-<api-svc>`. Mechanical; diff shape is −3/+1 per worker.
4. [ ] **Recurrence guard.** `scripts/compose_check.py` (stdlib-only, mirroring
   `notes_check.py`) asserting: no compose service declares both `command:` and `build:`, and
   every `image:` referencing a `finance-tracker-*` tag is built by exactly one service.
   Wire as `make compose-check` + a step in CI's `repo-lint` job.
5. [ ] **Verification — must be driven, not reasoned about** (see below).

## Verification

The failure mode of *this item* is a verification that lies, so the proof has to be a rebuild
the old setup would have gotten wrong:

1. `docker compose config --quiet` — the file still parses.
2. `docker compose config` before/after, diffed with the `build`/`image` keys stripped —
   proves the non-goal (nothing but the image source changed) across all 39 services.
3. Introduce a throwaway marker symbol in a **banking** worker's source
   (`app/workers/saga_command_consumer.py`), then run **only**
   `docker compose build banking-service` — the command that is broken today — followed by
   `docker compose up -d --force-recreate banking-saga-command-consumer`.
   `docker compose exec -T banking-saga-command-consumer grep -c <marker> …` must return `>0`.
   On master this returns `0`. banking is the right service because it is where the original
   incident happened and it has four workers.
4. Revert the marker, rebuild, confirm the stack comes up healthy:
   `docker compose ps` all `running`/`healthy`, then `make test-e2e`.
5. `docker images | grep -c finance-tracker` — expect the worker tags gone.

## Risks & rollback

- **Workers can no longer be built standalone.** With `image:` and no `build:`,
  `docker compose up -d <worker>` on a machine with no image will try to *pull*
  `finance-tracker-<svc>` from a registry and fail with `pull access denied`. 22 of 26 workers
  `depends_on` their API service, so Compose pulls the API into the up-set and builds it
  first; the four exceptions are `account-outbox-publisher`, `account-service-consumer`,
  `analytics-projection-consumer`, `analytics-embedding-consumer`. **Accepted deliberately**:
  the new failure is loud, rare and names the exact missing image, where today's is silent,
  common, and corrupts verification results. Adding `depends_on` to those four would fix the
  cosmetics but change startup ordering — a behaviour change this plan is not entitled to make.
- **Stale images already on disk.** After the swap, workers run whatever
  `finance-tracker-<svc>:latest` currently is — which for most services is today's build.
  A full `docker compose build` before the first `up` removes the ambiguity; step 3's marker
  test forces it anyway.
- Rollback is `git revert` of a compose-only commit. No data, no migrations, no API contracts.

## Outcome

2 commits: `f3534abb` (compose), `f42d0a43` (guard). E2E 24/24, stack 51/51 running.
CI green at `5a9d60df` (run `30282200565`, 18/18); the `Compose image-sharing check` step was
verified present and `success` in the `repo-lint` job, not merely inferred from the run's
conclusion — a skipped step and a passing step give the same colour at run level.

**The A/B was run rather than reasoned about**, because this is the one item whose failure
mode is a verification that passes. A marker comment went into
`banking-service/app/workers/saga_command_consumer.py`, then the *identical* command pair —
`compose build banking-service` + `up -d --force-recreate banking-saga-command-consumer` —
was run twice: once against `HEAD~2:docker-compose.yml` (control) and once against the new
file (treatment).

| | build exit | up exit | `ps` | marker in worker |
|---|---|---|---|---|
| control (old compose) | 0 | 0 | running | **0** |
| treatment (new compose) | 0 | 0 | running | **1** |

The control is the finding reproduced on demand: three green signals and stale code. The
treatment also propagated to the other three banking workers, none of which was named in any
command — which is the actual property being bought.

**Deviations from the plan:**

- **12 API services, not 10.** `ai-service` and `gateway-service` have no workers but still
  got the explicit tag, so the rule reads uniformly and the guard needs no exception list.
- **The old worker images are still on disk and will stay there.** The plan predicted the
  image count would drop; it went 56 → 44, and the 25 orphaned worker tags plus 6 from
  services deleted in June are still tagged, so `docker image prune` will not touch them —
  they need an explicit `docker image rm`. Compose no longer references any of them, so they
  are inert, not stale. Left to the user: deleting images is not a commit's business.
- **The guard grew a third check.** Beyond "no worker declares `build:`" it also asserts the
  project name is pinned and that every `finance-tracker-*` tag is built by exactly one
  service — the two ways the *fix itself* could be silently undone.
- **The hook needed a `set -e` fix that had nothing to do with P3-40.**
  `[ a ] || [ b ] && exit 1` aborts the whole hook when both checks pass, because the `&&`
  list then exits 1. Caught by running the hook in all four states instead of only the
  failing one.

**Verified-by-failing:** the guard was run against three deliberately introduced regressions
(re-grown `build:` block, typo'd tag nothing builds, removed `name:`) before it was believed.
A check that has only ever passed proves nothing.

**Spawned:** nothing new. Option 3 from the finding (git-SHA startup banner) is deliberately
not done — it makes staleness *visible*, and this makes it structurally impossible, so the
banner would now only serve deploys outside compose. P3-17 (workers skip migrations) remains
open and is the same root cause with a different symptom.
