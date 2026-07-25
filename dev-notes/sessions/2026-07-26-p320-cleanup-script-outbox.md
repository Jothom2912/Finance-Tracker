---
date: 2026-07-26
topic: P3-20 — cleanup script writes its delete events; ES reconciled to Postgres; CI feedback loop
---

# Session 2026-07-26 — P3-20 cleanup script joins the event contract

Direct continuation of [P1-13](2026-07-25-p113-budget-spend-from-analytics.md), which found
this and made it matter: budget-service now reads spend from the ES read model, so a phantom
row there inflates real money numbers.

## Done

**P3-20 shipped in 2 code commits** (`b0a9c2b7` fix + 5 unit tests · `c5cd9b90` ruff format).
Full detail in the [plan's Outcome](../plans/2026-07-26-p320-cleanup-script-outbox.md).

`scripts/cleanup_pg_duplicates.py` now writes a `TransactionDeletedEvent` outbox row in the
same transaction as its DELETE, built from the real contract class rather than hand-assembled
JSON. The existing publisher does the rest — nothing new was deployed.

| Account 1, expenses | Postgres | ES before | ES after |
|---|---|---|---|
| July | 53 / 17 528,17 | 54 / **17 666,17** | 53 / **17 528,17** |
| June | 84 / 16 709,83 | 85 / 16 739,83 | 84 / 16 709,83 |
| April | 36 / 9 345,02 | 37 / 9 465,02 | 36 / 9 345,02 |

Real-user phantoms 1 → **0**; rows missing in ES: 0 both before and after.

**One finding written** ([P3-21](../findings/2026-07-26-eval-seed-writes-to-prod-index.md)),
one resolved, and the durable rule added to
[patterns/transactional-outbox.md](../patterns/transactional-outbox.md).

**The CI feedback loop, carried over from 2026-07-25, was decided and shipped** in 2 commits
(`f02d8c74` drift fix · `5d3aa4a5` mechanism) —
[decision](../decisions/2026-07-26-ci-feedback-loop.md). Two layers: a tracked
`.githooks/pre-commit` running ruff on staged files (`make install-hooks`), plus a
`repo-lint` CI job covering `services scripts tests`. Detection remains unsolved and is
filed as **P3-22**.

## Learned / surprised

**My own finding under-counted the damage by 66×, because it diffed one month.** The P3-20
finding said "reconciling the existing drift is separate and cheap here (one row)". Diffing
the *full* id set instead of July returned 67 phantoms. The attribution was still correct —
exactly one real-user phantom, exactly the predicted row — but the confident "one row" came
from the scope of the query, not from the state of the system. Second time in two days that
re-measuring a committed finding changed it (P1-13 retracted a P2-25 claim the same way).
The pattern worth keeping: *a finding's blast radius inherits the narrowness of the query
that found it.*

**The other 66 are test fixtures living in the production index.** `es_seed.py` writes eval
data into `transactions_v2` with `is_deleted: false`. Harmless today — tenant filters keep
them out of real users' numbers — but they put a permanent floor of 66 under the exact diff
that detects this class of bug, so it cannot be automated into a must-be-zero assertion.
That is the real cost: not wrong numbers, but a disabled smoke detector. The check that
would have caught tx 1119 on day one is the one the fixtures block.

**Two real duplicates were sitting in the database, armed.** Running the *old* script that
day would have created two more permanent phantoms. The bug was not historical; it was
waiting. Deleting them with the fixed script turned a liability into the best available
verification — production-shaped data, not just my probe.

**Writing the fix surfaced its own inverse.** Guarding against "deleted without an event" made
the mirror case obvious: an event without a delete tombstones a *live* row, and since
`is_deleted` is terminal in ES, that is equally unrecoverable. A rowcount comparison before
commit costs three lines. It was not in the plan — implementing carefully is what found it,
which is an argument against planning in so much detail that implementation becomes
transcription.

**Verify with data the system produced, not data you inserted.** I created the throwaway pair
through the real API rather than with an INSERT, so ES held genuinely projected live
documents. Had I seeded Postgres directly, the delete event would have hit a non-existent ES
doc, `scripted_upsert` would have created a tombstone, the assertion would have passed — and
I would have proven nothing about flipping a live row. The control assertion mattered as much
as the positive one: the three *surviving* rows had to stay `is_deleted: false`.

**"Nobody watches CI" was the wrong diagnosis — the perimeter had holes.** I expected to find
a workflow problem and found the opposite: 12 services, 3 shared packages, frontend and e2e,
each with lint, format, bandit and tests. Thorough. What was missing is that the per-service
jobs lint only their own directory and the Makefile iterates the same list, so `scripts/` and
the root `tests/` were in **no** perimeter at all — and both had drift sitting on master.
`scripts/` is where the tools that write directly to production databases live. Had I gone
straight to "add a hook", I would have shipped a fix that still left those two directories
uncovered.

**The pipe trap bit me again while measuring the pipe trap.** My repo-wide
`ruff format --check ... | tail -15` printed two failing files and `EXIT=0`, because the
pipeline's status is `tail`'s — the exact mistake recorded in yesterday's log, made while
gathering evidence about that class of mistake. It is a good argument for why the gate has to
be a hook rather than a discipline: the hook does not depend on me reading output correctly.

**A commit hook must be written for bash 3.2.** My first draft used `mapfile` and `set -u`.
macOS ships bash 3.2 (2007), where `mapfile` does not exist and referencing an empty array
under `-u` is an error — so the hook would have failed on the only machine it runs on. Caught
by checking `bash --version` instead of assuming `#!/usr/bin/env bash` means a modern bash.

**Verifying a hook means proving it blocks, not that it is installed.** `git config` returning
`.githooks` proves nothing. I staged a deliberately broken file, confirmed the commit was
**not** created (HEAD unchanged), then confirmed `--no-verify` does get through, then that
clean code passes. The middle check matters: a hook with no escape hatch gets uninstalled the
first time it is wrong.

**Third documentation-vs-reality gap in the same script.** Its documented invocation
(`uv run python scripts/...`) cannot work — there is no root pyproject. It had never been
`ruff format`ed and carried an unused import, because `scripts/` is in neither
`PY_SERVICE_DIRS` nor CI. A directory holding tools that write directly to production
databases is outside every quality gate the services have.

## Open ends

- **P3-21** — eval fixtures in the production index. Blocks turning the Postgres↔ES id-set
  diff into an automated check, which is the durable fix for this whole class.
- **P3-22 — CI detection.** Prevention shipped; detection did not. A broken *test* on master
  is still invisible until someone opens a browser. Blocked on `gh auth login`, which is
  interactive and therefore the user's to run; after that a `make ci-status` target is
  trivial. The prevention layer covers lint/format only — that limit should not be read as
  coverage.
- **`make install-hooks` is silent if forgotten.** Per-clone and opt-in by design; the
  `repo-lint` job exists precisely because the hook cannot be relied on.
- **P2-25 unchanged** — this makes hard-delete event-correct, it does not decide soft-delete.
  The argument for soft-delete is marginally stronger now: it would make this leak class
  detectable by count rather than by id-set diff.
- Historical closed months keep their too-high surplus (unchanged from P1-13; June's and
  April's figures moved today, but no month was re-closed).
- Unchanged: P2-15, P2-21, P2-23, P2-24, P3-17, P3-18, P3-19.

## Notes updated

- Created `plans/2026-07-26-p320-cleanup-script-outbox.md`,
  `findings/2026-07-26-eval-seed-writes-to-prod-index.md`, this session log
- `findings/2026-07-25-cleanup-script-desyncs-read-model.md` → `status: resolved` + a
  "Resolved" section correcting the one-row claim
- `patterns/transactional-outbox.md` — new section: scripts are participants in the contract
- Created `decisions/2026-07-26-ci-feedback-loop.md`, `.githooks/pre-commit`
- `Makefile` — `install-hooks` + `lint-repo` targets; `.github/workflows/ci.yml` — `repo-lint` job
- `backlog/BACKLOG.md` — P3-20 done, P3-21 + P3-22 added
- `00-INDEX.md`
