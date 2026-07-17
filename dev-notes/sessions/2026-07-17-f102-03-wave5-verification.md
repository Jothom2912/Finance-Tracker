---
date: 2026-07-17
topic: F1-02/03 wave 5 — full verification (tests + live e2e) and close-out
---

# F1-02/03 wave 5: verification + bookkeeping

Waves 1–4 (contracts, rules API + engine scoping, correction consumer, frontend) were
shipped earlier today (`83ce7769`, `24d5a926`, `4e9e25d4`, `bb1a110f`, `5b2bcc6d`).
This session ran the plan's wave 5: test suites, live e2e on compose, docs.

## Step 10 — test suites: green

- contracts 44, transaction-service unit+integration (35 int), categorization-service 109,
  frontend 239 tests + eslint — all green.
- Remaining services via per-service `make check`: budget, goal, ai, saga, analytics,
  user all green; account + banking linted clean via `uvx ruff` (their Makefiles are
  pip-based — see below).
- **Root `make check` cannot pass locally as-is** (pre-existing, unrelated to F1):
  1. account/banking Makefiles call bare `ruff`/`pytest` (pip installs via
     `install-deps`) — fails when ruff isn't on PATH. Aligning them to uv is P3-01 scope.
  2. gateway `make check` fails on bandit B105 false positive (`token = ""` in
     `app/auth.py:51`, Low severity) because the service Makefile lacks CI's `-ll -ii`
     flags — this is exactly the Makefile-vs-CI bandit divergence awaiting a user
     decision (2026-07-16 log).

## Step 11 — live e2e on compose: PASSED

Stack was already rebuilt (images 13:11, after last code commit 12:20 — image-family
gotcha respected). Synthetic data only (real user-1 rows untouched); dev-JWT minted with
the compose secret. Bonus: a learned rule from the user's own manual frontend test
("shop n play" → Kiosk, id 131) already existed — the loop had fired live before this
session.

1. **Feedback loop**: CSV-imported synthetic merchant "E2E Smoke Cafeteria" →
   auto-categorized by a *seed* rule to Mad & drikke/Kaffebar ("cafeteria" keyword) →
   corrected via PUT to Underholdning & fritid/Oplevelser (tier flipped to `manual`) →
   learned rule (`merchant`, priority 10) visible on `GET /api/v1/rules/` after **~2s** →
   re-import of the same merchant landed in **Oplevelser, tier=rule**: the learned rule
   beat the longer seed keyword across tiers, exactly the TieredRuleEngine contract.
2. **User KEYWORD rule + TTL**: `POST /api/v1/rules/` ("e2esmokegym" → Fitness/sport,
   priority 50) → an import *seconds* later still hit fallback (consumer's 60s TTL
   overlay cache was stale — expected; `invalidate_user` only reaches the API process,
   see decision note §6) → an import after TTL expiry categorized correctly
   (tier=rule, no restart).
3. Cleanup: 4 synthetic transactions + 2 test rules deleted; rule 131 (user's own test)
   left in place.

## Step 12 — bookkeeping

- Decision note: [decisions/2026-07-17-learned-corrections-as-rules.md](../decisions/2026-07-17-learned-corrections-as-rules.md)
  (supersedes the `is_user_confirmed` merchant-upsert sketch in FEATURES).
- FEATURES.md: F1-02 + F1-03 → done. Architecture doc
  (categorization-and-ai-services.md) updated: rules pipeline, correction consumer,
  new event. Plan 2026-07-17 closed (status: done, outcome filled).

## Learned / operational notes

- `pyjwt` is nowhere in the venvs — mint dev tokens with `python-jose` (shared auth's
  lib), e.g. via user-service's venv.
- categorization rules API requires trailing slash (`/api/v1/rules/`; without → 307).
- Pre-existing leftover in taxonomy: category id 11 "E2E Cat 6b9dea2b" (from some earlier
  manual test, created before this session) — candidate for manual deletion.

## Open ends

- Root `make check` local-runnability (account/banking Makefiles + bandit flags) —
  P3-01 + the pending bandit-flags user decision.
- Next track decision (from 2026-07-17 loose-ends log): F1-04 goal-allocation demo story
  vs F1-01 notifications vs AI-plan tail (13–21). Recommendation: F1-04.
