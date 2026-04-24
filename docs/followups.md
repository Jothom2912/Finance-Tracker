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

## Amount encoding consistency sweep (2026-04-24)

Commit `9f8a27d` switched the canonical amount convention used by
`TransactionForm.jsx` from *signed amount* (negative for expenses) to
*positive amount + `transaction_type` enum*. This matches the backend
DTO (`CreateTransactionDTO.amount` with `ge=0.01`, direction carried
by the `transaction_type` field), and fixes a 422 on expense create.

The fix was verified not to regress the three frontend consumers that
a quick read uncovered (`TransactionsList` uses `Math.abs` + `type`;
`RecentTransactions` prefers `type` with an `amount < 0` fallback;
`SummaryCards` gets pre-aggregated totals from the monolith GraphQL
overview). The `amount < 0` fallback in
`services/frontend/src/components/RecentTransactions/RecentTransactions.jsx`
was kept and annotated as defensive code for legacy rows.

**Still to verify** (post Modal 2.2 browser verification, before
shipping to exam):

1. **CSV import path.** Walk `POST /transactions/import-csv` end-to-end:
   what does the frontend CSV parser send? If it sends signed amounts,
   we now have an asymmetry between manual create (positive) and
   import (signed). Start at `uploadTransactionsCsv` in
   `services/frontend/src/api/transactions.jsx` and follow into
   `services/transaction-service/app/application/service.py`
   (`import_csv` / line 249 `amount = Decimal(row["amount"])`).
2. **Edit flow.** `TransactionForm` preloads `setAmount(transactionToEdit.amount)`.
   If historical rows have negative amounts in the DB *and* new rows
   have positive amounts, the form will show a minus sign for old
   expenses but not new ones — inconsistent UX. Confirm the preload
   uses `Math.abs` or verify the DB is already uniformly positive.
3. **Aggregations.** Grep for any chart/summary code that uses
   arithmetic on `amount` (sum, reduce, comparison to 0) and confirm
   it disambiguates via `transaction_type` rather than sign. Known
   clean: `SummaryCards` (pre-aggregated by monolith),
   `TransactionsList` (display only). Known defensive:
   `RecentTransactions` (dual check, already annotated).
4. **Historical data.** Run a one-off query against the
   `transactions` table in Postgres: are existing rows uniformly
   positive, or is there a mix? If mixed, decide: (a) one-shot
   migration to normalise signs, or (b) leave historical data mixed
   and rely on `transaction_type` for all new reads. Neither is wrong;
   the point is that the decision is deliberate and documented.

**Priority:** medium. Nothing is broken today — the fix works and
tests pass. But an exam reviewer may ask "did you check for
asymmetric behaviour?" and the right answer is "yes, here is the
sweep I ran", not "I fixed the symptom I saw".

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

## Sweep discipline: Unicode regex for emoji/icon hunts (2026-04-24)

Lesson captured from the Phase 2.4 emoji → lucide-react sweep
(commit `bc77975`). The first `rg` pass used a regex that only
covered part of the Unicode symbol ranges and an explicit glyph
list derived from a stale plan document. It missed three
replacements: `✓`/`✗` (U+2713/U+2717) in `BankConnectionWidget`
and `📤` (U+1F4E4) in `CSVUpload`. A second, broader pass caught
them before the commit landed, but three round-trips would have
been one pass with the right regex upfront.

For future emoji/icon hunts, one combined regex covering:

* **U+2600–U+27BF** — dingbats + miscellaneous symbols.
  Catches `✓ ✗ ✕ ⚙ ▲ ▼ ☆ ★ ✏ ✅ ❌ ➤` etc. Easy to forget
  because these are often treated as "ASCII-ish" glyphs.
* **U+1F300–U+1F9FF** — pictographs (the "proper" emoji range).
  Catches `💰 📊 🎯 📤 💳 🚨 🟡` etc.
* **U+2300–U+23FF** — technical symbols. Catches `⌘ ⌥ ⏰ ⚠`
  (note: `⚠` at U+26A0 is in the 2600 range, but `⚠️` with the
  variation selector still matches on the base glyph).

Ripgrep syntax: `rg "[\x{2600}-\x{27BF}\x{1F300}-\x{1F9FF}\x{2300}-\x{23FF}]" path`.
Always do this before any "replace emojis with icons" or "audit
UI for non-themed glyphs" task. The regex is cheap; the round
trips are not.

Second lesson from the same commit: **the plan document is a
starting point, not ground truth.** Phase 2.4's plan listed 8
replacements; actual codebase scan found 14, split across 11
files. The planning document was written ~11 commits earlier
and the codebase had drifted. Lesson: every sweep starts with a
fresh `rg` pass against the current tree, not a re-read of the
plan. The plan tells you *what kind of work* to do; the `rg`
tells you *where it applies*.
