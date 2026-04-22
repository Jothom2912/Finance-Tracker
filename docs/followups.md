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


## Categorization fallback rate (2026-04-17, updated 2026-04-22)

Bank sync on 2026-04-17 produced 48 fallback-categorizations out of 206
transactions (~23 %).  Examples from the logs: `Seoul Koreansk BBQ`,
`KEBABBRO`, `ROSA KIOSK`, `OFF SITE MULTI OSTERBROGA`.

Either the rule-engine keyword catalog is incomplete for real-world
merchant names (restaurants, kiosks, location-prefixed strings), or
the ML/LLM tier described in the architecture is not yet wired up and
the fallback category is hit directly.

The baseline methodology — SQL queries against
`transaction-service`'s `transactions.categorization_tier`, paired
with three pre-defined decision thresholds — now lives in
`docs/categorization-baseline.md`.  That document replaces this
open-ended followup: any future "is fallback too high?" discussion
should start with a run of Q1/Q2/Q3 and land in one of the threshold
bands, not a new ad-hoc analysis.

Action: run the baseline queries against live data once the stack is
up, append the result row to the baseline table, and let the
threshold band dictate the next step (keyword expansion, normalization,
or planning an ML tier).  This followup stays open only until the
first baseline row is recorded.

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

## `start_bank_connection` + `bank_callback` still use catch-all → 502 (2026-04-22)

`sync_transactions` was rewritten in the same commit that introduced
`backend/banking/domain/exceptions.py`: domain exceptions now map to
404/409/500 explicitly, `TransactionServiceError` maps to 502, and
unclassified errors propagate to Starlette's default 500 handler.
The catch-all `except Exception → 502` was removed from that route.

The other two banking routes — `POST /bank/connect` and
`GET /bank/callback` — still swallow every exception into a 502, for
the same reason as before: they both call into
`EnableBankingClient`, which currently has no typed error hierarchy.
`httpx.HTTPStatusError`, JWT-signing failures, and anything else
come out looking identical.  Mapping them properly requires first
introducing an `EnableBankingError` (or a small family:
`BankAuthorizationError`, `BankApiUnavailable`, `BankConfigError`)
so the route layer has something concrete to pattern-match on.

Deferred deliberately rather than retrofitted under the current
commit — cleaning up the route without a typed adapter error would
just move the catch-all one layer down, not eliminate it.

Action (future commit):
1. Introduce `EnableBankingError` hierarchy in
   `backend/banking/adapters/outbound/enable_banking_client.py`, used
   by `create_session`, `start_authorization`, and the PEM / JWT
   handling in `__init__` / `_get_jwt`.
2. Rewrite the `except Exception` blocks in
   `start_bank_connection` and `bank_callback` to map the new types
   explicitly, following the `sync_transactions` pattern.
3. Add route-integration tests mirroring
   `tests/integration/test_bank_sync_routes.py` — including a
   positive control that unclassified errors reach the 500 handler.
