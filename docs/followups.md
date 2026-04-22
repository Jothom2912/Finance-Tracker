# Open Follow-ups

Ongoing list of known issues and improvements deferred from active work.
Not a replacement for an issue tracker — these are items not yet
formalized. Reference entries from commit messages and ADRs as needed.

## `display_order` missing on API-created categories (2026-04-17)

After migrating category ownership to transaction-service (see
`docs/retrospective-transaction-ownership.md`), `CategoryCreatedEvent`
deliberately does not carry `display_order` because it's a monolith-only
UI-presentation concern.  `CategorySyncConsumer._sync_created` in
`services/monolith/backend/consumers/category_sync.py` therefore projects
new categories with MySQL's column default (`display_order=0`).

For the ten default categories this is fine: `seed_categories.py` sets
their display_order explicitly from `DEFAULT_TAXONOMY`.  For categories
created later via transaction-service's `POST /api/v1/categories/` API,
the projected row sorts to the top of the UI list (0 < seeded values
1–20) rather than appending at the end like the user would expect.

Not a drift bug — projection is consistent — but a latent UX regression
introduced by the ownership split.  Two plausible fixes:

* Auto-assign `display_order = MAX(display_order) + 1` in the sync
  consumer when a new category is projected.
* Expose `display_order` as an optional field on the category API and
  add it to the event contract, accepting that this elevates a UI
  concern into the cross-service model.

No action until a user actually creates a new category and notices the
sort order; quantify the pain before picking a fix.

## Testcontainers Ryuk on Windows / Docker Desktop (2026-04-17)

`services/transaction-service/tests/migrations/conftest.py` sets
`TESTCONTAINERS_RYUK_DISABLED=true` because the reaper container fails
to get its port mapping on Docker Desktop for Windows (observed during
the session that introduced the migration tests).  The trade-off is
that test containers aren't auto-reaped on an orphaned test run — the
session-scoped fixture's explicit `container.stop()` handles cleanup
on normal paths, but a hard pytest crash may leave containers around.

Linux CI is unaffected; this is a local-dev quirk only.  Revisit when
either (a) a future Testcontainers release fixes the Windows case, or
(b) the Windows dev workflow produces enough orphaned containers to
become annoying in practice.


## Categorization fallback rate (2026-04-17, closed 2026-04-22)

Bank sync on 2026-04-17 produced 48 fallback-categorisations out of
206 transactions (~23 %).  The baseline methodology — Q1/Q2/Q3
against `transaction-service`'s `transactions.categorization_tier`
with three pre-defined decision thresholds — lives in
`docs/categorization-baseline.md`.  The first baseline row was
recorded on 2026-04-22 (N=205, 23.4 % fallback).

This item is closed because the baseline table is now the active
record; future "is fallback too high?" questions start with a Q1/Q2/Q3
run and land in one of the threshold bands, not a new ad-hoc analysis.
Concrete action items produced by that baseline (keyword expansion,
normalisation, ML tier) are tracked as their own commits or
followups.

## Bank date edge case (2026-04-17)

The Enable Banking adapter now fails fast when both `booking_date` and
`value_date` are missing from a transaction payload (see
`services/monolith/backend/banking/adapters/outbound/enable_banking_client.py`).
The previous behaviour was silent corruption: the adapter returned
`BankTransaction(date="")` and the error only surfaced downstream as an
obscure `AttributeError: 'str' object has no attribute 'isoformat'`.

The failure path is handled by the existing `try/except` in
`BankingService.sync_transactions`, which logs the exception and
increments the error counter, so a single malformed payload no longer
breaks the whole sync batch. However, the log line is a raw `ValueError`
from `date.fromisoformat` without a bank-specific context.

Action: wrap the parse failure in a `BankParseError` (or similar
domain-specific exception) if and when distinguishing parse errors from
other sync failures becomes valuable in logging or metrics. YAGNI for
now — one line of error counter is enough until a real operational need
appears.

**Observed on 2026-04-17**: The first post-fix sync against the live
Enable Banking account skipped 1 of 206 transactions (0.48%). Confirms
the edge case exists in real bank data but at a low enough rate to
stay in WARNING-log territory. Worth tracking across multiple syncs;
a rising rate would indicate a broader data-quality issue upstream
at Enable Banking or the specific bank ASPSP.

## `start_bank_connection` + `bank_callback` still use catch-all → 502 (2026-04-22, closed 2026-04-22)

Closed by the same-day follow-on commit that introduced
`EnableBankingError` / `BankConfigError` / `BankApiUnavailable` /
`BankAuthorizationError` in
`backend/banking/adapters/outbound/enable_banking_client.py`.  All
three banking routes now map typed adapter errors explicitly:

* `BankConfigError`       → 500  (our deploy is misconfigured)
* `BankApiUnavailable`    → 502  (upstream unreachable or 5xx)
* `BankAuthorizationError` → 400  (callback's `auth_code` rejected,
  raised only from `create_session`)

Every `except Exception` catch-all on the banking routes was removed.
Each route has a positive-control test asserting an uncaught
`RuntimeError` reaches Starlette's default 500 handler, so a future
reviewer who reintroduces a catch-all breaks CI.

## Enable Banking config not validated at startup (2026-04-22)

`_get_client()` in
`backend/banking/presentation/rest_api.py` instantiates
`EnableBankingConfig` + `EnableBankingClient` lazily on the first
request that touches a banking route.  Both constructors now raise
`BankConfigError` on misconfiguration (missing `ENABLE_BANKING_APP_ID`,
unreadable PEM), and the route maps that to HTTP 500 — so the user
who clicks "Connect bank" first gets the 500.

The honest failure mode would be a fail-fast check at app startup so
misconfiguration surfaces at deploy time, not at first user traffic.
Two plausible shapes:

1. Call `_get_client()` from a FastAPI `startup` event (or
   `lifespan` context) and let `BankConfigError` crash the process.
2. Add a `validate()` method on `EnableBankingConfig` that the DI
   wiring calls during container build.

Deferred because the current deployment flow (local Docker Compose
for development, no prod yet) doesn't make first-user-500s visible in
a painful way.  Revisit before any real-user deploy.

## Bank-callback redirects render raw JSON in the browser (2026-04-22)

`GET /api/v1/bank/callback` is the redirect target after the user
completes the Enable Banking OAuth flow.  It is called by the user's
browser, not by the frontend SPA — there is no frontend handler for
this path (confirmed by grep across `services/frontend/src`).
Current behaviour on *any* outcome (success or failure) is:

```
{ "detail": "Bank authorization rejected: ..." }
```

rendered as raw JSON in a browser tab.  The HTTP status is now
correctly typed (400 / 500 / 502 per the adapter error) but the UX is
still "user sees raw JSON and has no idea what to do".

The proper fix is one of:

1. Redirect to a frontend error page with the status as a query
   parameter (e.g. `http://localhost:3000/bank/connected?error=rejected`).
2. Render a minimal HTML error template from the monolith for the
   callback path specifically.

Out of scope for the typed-errors commit — picking a pattern is a
frontend/UX conversation.  Current typed JSON responses at least give
a frontend error page something to branch on once it exists.

## Duplicate transactions in MySQL projection (2026-04-22)

Surfaced while verifying dual-write status for the categorisation
baseline (see `docs/categorization-baseline.md`).  The MySQL
`Transaction` table holds **431 rows** while PostgreSQL
(`transaction-service`, source-of-truth) holds only **205**.  The
delta is 226 rows distributed across two pre-`transaction-service`
sync batches:

| Import day | N   | Earliest tx | Latest tx   |
|------------|-----|-------------|-------------|
| 2026-03-26 |  92 | 2025-12-29  | 2026-03-26  |
| 2026-04-03 | 134 | 2026-01-05  | 2026-04-07  |
| 2026-04-17 | 205 | 2026-01-19  | 2026-04-16  |

The date ranges overlap heavily, and a `GROUP BY (description, date,
amount) HAVING COUNT(*) > 1` returns **172 duplicate triplets** —
the same real-world transaction imported two or three times because
the monolith's bank sync had no dedup before `transaction-service`
took over transaction ownership.

Scope and impact:

* `categorization_tier` itself is **not** divergent — it has a
  single writer (monolith's rule engine at write-time, sent to
  `transaction-service`, projected back via
  `transaction_sync_consumer`).  Each individual row's tier is
  consistent between DBs.
* The duplicated rows do skew **analytics against MySQL**: any
  aggregation over the overlapping date ranges (Overview totals,
  per-category rollups in the monolith's GraphQL API) double- or
  triple-counts transactions.  Dashboards rendered from
  `transaction-service` are unaffected.

Not acting now because the fix is a scope-conversation, not a
one-line change:

1. **Delete duplicates in MySQL.**  Keep the most recent import per
   `(description, date, amount)` or reconcile against the 205
   `transaction-service` rows and keep only the matching ones.
   Cheapest; loses the pre-`transaction-service` history in MySQL.
2. **Backfill `transaction-service`** with the 226 older rows so the
   two DBs converge forward.  Requires replaying those rows through
   the current categorisation pipeline (tiers may now classify them
   differently than the original sync did).
3. **Leave as-is** and document that any analytic query against the
   monolith's MySQL must de-duplicate before aggregating.  Pragmatic
   stop-gap — but the "any query" scope makes it brittle.

Pick one when either (a) someone hits a wrong number in the UI, or
(b) the wider microservice extraction reaches a point where MySQL
is being decommissioned and this has to be decided anyway.
