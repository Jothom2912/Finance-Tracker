# Status — 2026-07-27

Where the work stands right now. **Read this first**; it exists so a session does not start
by guessing which of 32 plans is live. Update it when the active plan changes, an item
finishes, or a session ends — a stale STATUS.md is worse than none.

Everything here is derivable from the backlog and plan statuses; this file is a shortcut,
not a second source of truth. If it disagrees with `backlog/BACKLOG.md`, the backlog wins.

## Active

Nothing in flight. The last piece of work (P1-15 + P2-26) shipped 2026-07-27 with CI green
(run `30266231499`).

## Next up

- **P2-21** — k8s manifest drift: 6 workloads + 1 DB in compose have no manifest, so
  `apply -k` silently drops the notification feed and the automatic ADR-0003 chain.
- **P2-25** — transaction soft-delete + gone-vs-not-yet in the categorization write-back
  (the only P2 that is a data-model decision, so it gates P3-37).
- **P2-27/28/29** — rate limiting, taxonomy write auth, CSV upload bounds. All from the
  product-surface sweep; each is small and independent.

## Open findings worth knowing before you touch anything

| Finding | Severity | Scheduled as |
|---|---|---|
| [product-surface sweep](findings/2026-07-26-product-surface-sweep.md) | HIGH | P2-26..29, P3-24..34, F2-08..13 |
| [k8s manifest drift](findings/2026-07-25-k8s-manifest-drift.md) | MEDIUM | P2-21 |
| [transaction hard-delete → DLQ](findings/2026-07-25-transaction-hard-delete-categorized-dlq.md) | MEDIUM | P2-25 |
| [per-worker image staleness](findings/2026-07-25-per-worker-image-staleness.md) | MEDIUM | **nothing — unscheduled** |
| [worker migration ordering](findings/2026-07-25-worker-migration-ordering.md) | LOW | P3-17 |
| [eval seed writes to prod index](findings/2026-07-26-eval-seed-writes-to-prod-index.md) | LOW | P3-21 |
| [non-UUID saga_id poison](findings/2026-07-25-saga-reply-non-uuid-poison.md) | LOW | P3-19 |

**Per-worker image staleness has no backlog item.** It matters out of proportion to its
severity because it makes *live verification lie*: `compose build <service>` does not
rebuild that service's workers, so a manual test can pass against old code. Grep the
running container before believing a live test.

## Standing traps

- `account-service` and `banking-service` are pip-based with no venv: `make test` / `make lint`
  fail locally regardless of the code. banking's suite runs **only** in CI. See P3-39.
- Never pipe a verification command through `tail`/`head` — the pipeline's exit code is the
  last command's, so `check | tail && git commit` commits on a failing check.
- `make ci-status` for the current branch's CI; `make notes-check` before committing notes.
