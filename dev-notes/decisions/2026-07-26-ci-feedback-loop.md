---
title: Two-layer ruff gate — pre-commit hook plus a repo-wide CI lint job
date: 2026-07-26
status: accepted
supersedes: null
promoted-to-adr: null
---

# Two-layer ruff gate — pre-commit hook plus a repo-wide CI lint job

## Decision

A tracked `.githooks/pre-commit` runs `ruff check` + `ruff format --check` on staged
`.py` files (installed once per clone via `make install-hooks`), **and** a new `repo-lint`
CI job runs the same two commands across `services scripts tests`. Neither replaces the
other: the hook catches the failure where it is cheapest, the CI job is the only thing that
can actually guarantee anything about master.

Tests stay out of the hook.

## Context

On 2026-07-25 three CI jobs — banking-service, budget-service, and the three shared
packages — were discovered red **by accident**, during unrelated work. All three failed on
`ruff format --check` against already-committed code. Because that step precedes the test
step, budget-service's 117 tests had not run in CI for five days.

Three independent instances in a single day is a missing feedback loop, not three mistakes.
The session log for that day filed it as needing a mechanism decision rather than another
`ruff format` commit. This is that decision.

Measurement taken before choosing ([session](../sessions/2026-07-26-p320-cleanup-script-outbox.md)):

- **The CI workflow itself is not the problem.** 12 services + 3 shared packages + frontend
  + e2e, each with lint, format, bandit and tests. The content is thorough.
- **The perimeter has holes.** The per-service jobs lint only their own directory, and the
  Makefile's `lint` target iterates the same `PY_SERVICE_DIRS` list. `scripts/` and the root
  `tests/` are in neither. A repo-wide run found drift in both
  (`scripts/backfill_category_names.py`, `tests/e2e/test_budget_threshold_alert_e2e.py`).
  This is the same hole P3-20 hit, where `cleanup_pg_duplicates.py` — a tool that writes
  directly to a service database — had never been formatted or linted.
- **There was no preventive gate at all.** `.git/hooks/` was empty.
- **There is no detection either.** `gh` is not authenticated locally, so there is no path
  to CI status short of opening a browser.
- **One fact makes the fix cheap**: no service defines its own `[tool.ruff]`. Everything
  inherits the root `ruff.toml`, so a single invocation from the repo root is correct
  repo-wide — no per-service venv, no matrix.

## Alternatives considered

- **CI job only** — no workflow change to install, nothing to bypass. Rejected as the sole
  measure because it only reports *after* push, and "nobody looks at Actions" is precisely
  the situation being fixed. It would have detected the three red jobs no faster.
- **Hook only** — catches the error before it enters history, which is where it is cheapest.
  Rejected as the sole measure because hooks are per-clone (`.git/hooks` is not cloned),
  opt-in, and bypassable with `--no-verify`. A gate that can be silently absent guarantees
  nothing about master.
- **Tests in the hook** — would have caught more than formatting. Rejected: 12 services is
  far too slow for a commit hook, and a slow hook gets disabled, which is worse than no
  hook. CI already runs them, and the observed failure class was 100% lint/format.
- **`pre-commit` framework** — more capable, standard, extensible. Rejected as
  disproportionate: it adds a dependency and a config format to solve a problem that is
  two ruff invocations in a 70-line bash script, in a repo with one developer.
- **Auto-format in the hook instead of blocking** — rejected: rewriting files underneath a
  commit is surprising, and it would silently include unreviewed changes in the commit.

## Consequences

**Easier.** Formatting drift cannot reach master unnoticed through either layer. `scripts/`
and `tests/` are inside a perimeter for the first time. `repo-lint` needs no dependency
install, so it reports in well under a minute rather than after twelve `uv sync`s — the
fastest signal in the workflow is now also the one that was failing most often.

**Harder.** One extra setup step per clone (`make install-hooks`), and it is silent if
forgotten — the CI job is the mitigation for exactly that. Commits now take ~1s longer.

**Explicitly not solved: detection.** Knowing that CI went red still requires looking. That
needs `gh auth login`, which is interactive and therefore a user action. Once authenticated,
a `make ci-status` target or a session-start check becomes possible. Until then this
decision is prevention-only, and that limit should not be mistaken for coverage.

**Not solved either: the pipe trap.** `uv run ruff check . | tail -2 && git commit` commits
even when ruff fails, because the pipeline's exit status is `tail`'s — it cost a fixup
commit on 2026-07-25 and recurred while measuring for *this* decision. The hook makes it
harmless for lint and format specifically, since the gate no longer depends on the developer
reading command output correctly. It remains a live trap for every other piped check.
