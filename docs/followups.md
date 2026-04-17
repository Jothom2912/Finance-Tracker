# Open Follow-ups

Ongoing list of known issues and improvements deferred from active work.
Not a replacement for an issue tracker — these are items not yet
formalized. Reference entries from commit messages and ADRs as needed.

## Categorization fallback rate (2026-04-17)

Bank sync on 2026-04-17 produced 48 fallback-categorizations out of 206
transactions (~23%). Examples from the logs: `Seoul Koreansk BBQ`,
`KEBABBRO`, `ROSA KIOSK`, `OFF SITE MULTI OSTERBROGA`.

Either the rule-engine keyword catalog is incomplete for real-world
merchant names (restaurants, kiosks, location-prefixed strings), or the
ML/LLM tier described in the architecture is not yet wired up and the
fallback category is hit directly.

Action: audit the rule-catalog coverage against a sample of real bank
descriptions before investing in an ML/LLM tier. A 23% fallback rate
implies the rule tier alone is not sufficient as the primary
categorizer; quantify which categories the fallbacks are routed to
before deciding where to spend engineering time.

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

## HTTP status code mapping for ValueError (2026-04-17)

`rest_api.py:212-213` maps any `ValueError` to HTTP 404. This is
semantically wrong — 404 means "resource not found", but `ValueError`
from downstream services typically means "resource found but input
invalid". Correct status codes would be 422 (Unprocessable Entity) or
400 (Bad Request).

Surfaced during bank sync debugging: a per-transaction parse error in
the adapter bubbled up as a 404 response to the API client, making the
root cause invisible without reading service logs.

Action: audit all `ValueError` → `HTTPException` mappings in
`rest_api.py`. Consider introducing domain-specific exception types
(`ParseError`, `ValidationError`) that map to appropriate status codes.
