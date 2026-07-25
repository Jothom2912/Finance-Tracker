---
title: banking-service's CI job could never run its tests (and shared packages were not in CI at all)
date: 2026-07-25
severity: MEDIUM
area: infra / CI
status: resolved
resolved-by: commits 023970ba (conftest), 7f13173f (shared-packages job) — [plan](../plans/2026-07-25-p222-saga-inbox-and-loose-ends.md) steps 6 + 6b
---

# banking-service's CI job could never run its tests

**Where**: `.github/workflows/ci.yml` (job `python-services`, matrix entry `banking-service`);
`services/banking-service/app/config.py:43`; missing `services/banking-service/tests/conftest.py`.

**Defect**: `Settings` requires `DATABASE_URL` (no default, and there is no committed
`.env`), so importing anything under `app` raised `ValidationError` at pytest **collection**
time. The workflow sets `JWT_SECRET`, `TESTING` and `INTERNAL_API_KEY` — but not
`DATABASE_URL` — and banking-service was the one service with no `tests/conftest.py` to set
it. `pytest tests` therefore could not collect, ever.

Separately: the three shared packages (`contracts`, `messaging`, `auth`) were not in CI at
all, and all three were failing `ruff format --check` on committed code.

**Why it matters**: P2-14 (2026-07-07) added banking-service to the CI matrix and the
backlog records that as done — so the row said "covered" while the job could not execute a
single test. Worse, the failure was **masked**: `ruff format --check` runs before the test
step in the same job, and banking-service was also failing that check, so the job aborted
early and the collection error never surfaced. Commit d5630a6e (notification-hardening,
2026-07-25) fixed the formatting and thereby uncovered this — meaning that between
2026-07-07 and 2026-07-25 the banking-service job was red for a *cosmetic* reason that hid
a structural one.

This is the same failure class as the two live-verification notes in these dev-notes: a
green-looking signal that never exercised the thing it claimed to cover. Here the signal was
red, which is better, but for the wrong reason — and a job that is *always* red teaches
people to ignore it, which costs the same as a false green.

The shared-package gap is the higher-leverage half: all 12 services import those packages,
so a break there is broader than a break in any single service, and nothing was checking.

**Fix applied**:
1. `services/banking-service/tests/conftest.py` in the same shape as the other seven
   services' — sets `JWT_SECRET`/`DATABASE_URL` and puts the service root plus
   `shared/{contracts,messaging,auth}` on `sys.path`. banking-service has no
   `pyproject.toml`, so the path setup cannot come from a package install. `pytest tests`
   now runs bare, with no env and no `PYTHONPATH` — i.e. exactly as CI calls it. This also
   retires the awkward `uv run --with-requirements …` incantation the
   notification-hardening plan had to document as a gotcha.
2. New `shared-packages` CI job (own matrix over the three packages). It could not be matrix
   entries in `python-services`: that job's bandit step hard-fails without an `app/`
   directory, and these are libraries. The packages also still used
   `[project.optional-dependencies] dev` without `ruff`, so `uv sync --dev` (PEP 735
   dependency-groups, which CI and all 12 services use) installed no tooling and `uv run
   ruff` failed with "Failed to spawn" — migrated to `[dependency-groups]`.

**Still open**: nothing here, but the general lesson belongs with P3-13's CI-coverage work —
a CI job whose *test step* never executes should be detectable. A minimum-collected-tests
assertion (`pytest --collect-only` count > 0) per service would have caught this on day one.
