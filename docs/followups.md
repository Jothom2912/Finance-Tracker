# Open Follow-ups

Ongoing list of known issues and improvements deferred from active work.
Not a replacement for an issue tracker — these are items not yet
formalized. Reference entries from commit messages and ADRs as needed.

## `display_order` missing on API-created categories (2026-04-17, closed 2026-04-23)

Closed by the commit that added `COALESCE(MAX(display_order), 0) + 1`
in `CategorySyncConsumer._sync_created`.  New categories now append at
the end of the UI list.  The fix is a single-statement read + ORM
insert (not INSERT...SELECT), with a comment acknowledging the
theoretical race condition — acceptable because the consumer is the
sole writer to this table, enforced by `test_read_only_projections.py`.

## Testcontainers Ryuk on Windows / Docker Desktop (2026-04-17, mitigated 2026-04-23)

Still present — Ryuk remains disabled on Windows.  Mitigation:
`make clean-test-containers` target added to the root Makefile to
remove orphaned containers by the `org.testcontainers=true` label.
The conftest comment already explains the trade-off.  Revisit when
a future Testcontainers release fixes the Windows case.


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

## Enable Banking config not validated at startup (2026-04-22, closed 2026-04-23)

Closed by adding `validate_banking_config()` in
`backend/banking/presentation/rest_api.py`, called from the monolith
`lifespan`.  Three config states are handled:

* All `ENABLE_BANKING_*` vars absent → info log, banking disabled
* Partial config (some vars set, others missing) → `BankConfigError`
  logged as error (half-finished deploy)
* Full config → PEM readability checked, IO errors wrapped in
  `BankConfigError`

The lifespan catches `BankConfigError` and logs but does not crash,
so the rest of the app stays available.

## Bank-callback redirects render raw JSON in the browser (2026-04-22, closed 2026-04-23)

Closed by replacing JSON responses with `RedirectResponse` (HTTP 303)
to a new frontend page at `/bank/callback`.  Error codes (not raw
exception text) are forwarded as query params; a server-side
correlation ref is included for support lookups.

The frontend `BankCallbackPage` maps short codes to user-friendly
Danish messages via a local lookup table and never renders URL params
directly as HTML, avoiding both information leakage and XSS surface.

## Duplicate transactions in MySQL projection (2026-04-22, cleanup script ready 2026-04-23)

A reconciliation script was added at `scripts/cleanup_mysql_duplicates.py`
with the following safety rails:

* `--dry-run` is the default (shows counts and sample rows)
* `--execute` triggers mysqldump backup before deletion
* Every deleted row is logged as full JSON to `scripts/backups/`
* Idempotent — second run finds 0 orphans

**Root cause:** the old monolith bank sync wrote directly to MySQL
without deduplication.  The current path goes through
`transaction-service`'s `POST /bulk` with `skip_duplicates=True`.
The old direct-write path was removed and architecture test
`test_read_only_projections.py` blocks any non-consumer writes to
the Transaction model, preventing recurrence.

**Run with** `make cleanup-mysql-duplicates-once` (dry-run) or
`make cleanup-mysql-duplicates-once EXECUTE=1` (delete).
**Remove the script and Makefile target after running.**
