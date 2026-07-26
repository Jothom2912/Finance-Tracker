---
date: 2026-07-26
topic: Product-surface sweep — what the backlog was not looking at
---

# Session 2026-07-26 — product-surface sweep

Documentation only. No code changed; nothing to deploy.

## Done

Four parallel read-only reviews (user-service + auth surface; frontend UX/a11y; security
posture; performance & ops), each told to read BACKLOG.md first and report only what is
**not** already P1-01…P3-23. Results verified by hand against source, and for the two
serious ones, against the running stack.

Written:

- `findings/2026-07-26-product-surface-sweep.md` — the survey (11 SEC · 8 UX · 7 OPS)
- `findings/2026-07-26-transaction-list-truncated-at-50.md` — → P1-14
- `findings/2026-07-26-categorize-endpoint-unauthenticated.md` — → P1-15
- BACKLOG.md: P1-14, P1-15, P2-26…P2-29, P3-24…P3-34, + dated corrections on P2-02 and P2-19
- FEATURES.md: F2-08…F2-13

## Learned / surprised

**The user domain was never written.** This is the sweep's structural result and it
reframes several unrelated-looking gaps. `user-service` has four endpoints; `users` has
five columns unchanged since migration 001; the repository has `create` and three
`find_by_*` and **no write path to an existing user at all**. Every other bounded context
got extracted, hardened and given a saga; this one still has its day-one shape. The person
using a financial platform cannot change their own password, and there is no deletion, no
export, no retention — with PSD2 bank data, in Denmark.

The part worth keeping for the exam: **database-per-service turns the right to erasure into
a distributed transaction.** A user's data spans six services with no cross-service delete
orchestration and no `UserDeletedEvent` in the contracts. That is exactly what saga-service
is for, and it is the one job nobody has given it. Nice symmetric point to the ADR-0003
money flow — the same machinery, run for a compliance obligation instead of a feature.

**P1-13 has a twin, and I only fixed one half.** The transactions page sends no `limit`
against the same `limit=50` default, applied after the same `ORDER BY date DESC`. June has
93 rows in Postgres; the page can show 50. Worse than a standalone bug: since P1-13 the
dashboard reports June correctly at 16 739,83 across 93 transactions while the list shows
50 of them, so a *correct* total now sits above rows that cannot add up to it. Fixing the
computation without fixing the presentation made the discrepancy visible instead of
resolving it. Lesson for the next truncation-shaped finding: grep every call site of the
endpoint, not just the one that motivated the investigation.

**"Done" kept meaning "built", not "switched on".** Two rows overstate what shipped:

- P2-02 has `require_exp` in its title — the flag exists and defaults to `False`, and no
  call site opts in across all 12 services.
- P2-19 says "prefetch >1 where idempotent" — every consumer is still at 1, including the
  shared default.

Same pattern as the event-delivery exam note. Neither is causing damage today; both make
the backlog claim a ceiling was raised when it was not. Corrected in place with dated notes
rather than by editing the original claims.

**Live verification changed the severity of one finding and would have changed my
confidence in another.** `/categorize` reads plausible in source — an S2S endpoint with the
user scope in the body, docstring and all. It only becomes obviously critical when you
curl it with no credentials and watch `"SHOP N PLAY"` return `tier:"fallback"` for
`user_id` null and 2 but `tier:"rule", confidence:"high"` for `user_id:1`. Reading the code
gives you "missing auth dependency"; running it gives you "unauthenticated enumeration of a
stranger's spending habits". Worth the two minutes every time.

**The frontend is better than the notes imply.** Design tokens are complete, Radix dialogs
have real focus management (including deliberate DOM order so Enter cancels), toasts have
correct paired live regions, empty states are broad and action-oriented, confirmation copy
is genuinely well written, and there is no XSS sink anywhere. The gaps are real but they
are gaps in a decent baseline, not a bad frontend. Recorded that explicitly in the sweep so
the next reader calibrates correctly.

**Runtime performance needs no work; the build layer does.** 359 ES documents, empty DLQs,
no queue backlog, CI under 72 s per job, 220 tests in 14 s. Meanwhile: 57 GB of images, a
1,7 GB build context, the shared packages' dev `.venv` baked into all 12 images (~92 MB
each), and an 874 KB frontend bundle served uncompressed because gzip is off in nginx. I
went looking for slow queries and found none — the cost is entirely in distribution.

Also: no `.dockerignore` means `frontend/Dockerfile` copies the host's darwin-arm64
`node_modules` over the linux ones it just installed. It works today only because nobody
has run `npm install` locally before a build at the wrong moment.

## Open ends

Nothing is in flight. The filed work in recommended order:

1. **P1-14** — verify the truncation from the UI (create 60 tx on one account, count the
   list), then decide the response shape: envelope vs `X-Total-Count`. That decision gates
   the implementation and is worth a decision note.
2. **P1-15** — `require_internal_api_key` on the categorize router + `max_items`, and
   rotate the shared HS256 secret out of `k8s/secrets.yaml` in the same change. Ship
   **P2-26** (`require_exp=True`, one line × 12) with it: the two together are what turns a
   leaked key from permanent access into 60-minute access.
3. **P3-28 + P3-29** — the build/ops afternoon. Measured, low risk, felt in every
   subsequent build.
4. **F2-08** — plan-first. Read sweep §0 for the `UserUpdatedEvent` constraint before
   designing anything, and settle the email question (P3-18) before F2-09 rather than
   during it.

Two things deliberately **not** filed as actionable items because they need a decision
first, not an implementation:

- **P3-24** — whether the gateway should be a perimeter at all. A portfolio system may
  reasonably say no; it should say so in an ADR. The datastore-port half is free either way.
- **P2-28** — taxonomy authorisation needs a role concept that does not exist anywhere in
  the codebase, so it couples to F2-08's user-model work.

## Notes updated

Created: three findings, this session log.
Updated: `backlog/BACKLOG.md` (2 P1, 4 P2, 11 P3, 2 corrections), `backlog/FEATURES.md`
(6 F2), `00-INDEX.md` (3 finding lines).
