---
title: The transaction list endpoint returns a {total_count, items} envelope
date: 2026-07-26
status: accepted
supersedes: null
promoted-to-adr: null
---

# The transaction list endpoint returns a `{total_count, items}` envelope

## Decision

`GET /api/v1/transactions/` changes from `list[TransactionResponse]` to
`{"total_count": int, "items": [...]}` — the shape already used by
`analytics-service`'s `TransactionSearchResultDTO` and the gateway's
`TransactionSearchResultType`. `total_count` counts every row matching the filters,
**ignoring** `skip`/`limit`.

This is a deliberate, unversioned breaking change. Both callers are in-tree and both are
updated in the same plan ([P1-14](../plans/2026-07-26-p114-transaction-list-pagination.md)).

Two consequences are accepted rather than worked around: `total_count` and `items` can
disagree by a row under concurrent writes, and the frontend carries a temporary
shape-tolerant reader so the change has no deploy-skew window.

## Context

[P1-14](../findings/2026-07-26-transaction-list-truncated-at-50.md): the transactions page
shows 50 of June's 93 rows, and because the cut lands after `ORDER BY date DESC` what
disappears is the oldest part of the selected period. Fixing it needs two things — a way for
the client to ask for the next page, and a way for the client to know a next page exists. The
first already works: the endpoint has taken `skip`/`limit` since P1-07. Only the **total** is
missing, and a total has nowhere to live in a bare JSON array. So the fix forces a
response-shape decision on the endpoint the product's main surface reads.

Three facts constrained the choice, all verified rather than assumed:

**The shape already exists in this codebase, twice.**
`analytics-service/app/application/dto.py:71-73` defines
`TransactionSearchResultDTO {total_count, items}`, and
`gateway-service/app/adapters/inbound/graphql_api.py:209-212` mirrors it as
`TransactionSearchResultType`. It is not an accident of one author: the DTO immediately below
it, `HybridSearchResultDTO`, deliberately *omits* `total_count` with a comment that fused
ranks have no meaningful total — so the convention has been reasoned about. It has three
consumers: the gateway's `analytics_client.py:178`, `ai-service`'s
`analytics_client.py:143` (which uses the total to decide whether a page is complete, exactly
the question P1-14 needs answered), and the frontend's `useTransactionSearch`, which is what
already renders "X af Y resultater" on the very page this finding is about. `X-Total-Count`,
by contrast, appears **nowhere** in the repo — zero hits across `.py`, `.ts`, `.tsx`, `.yaml`.

**The browser talks to transaction-service directly.** `serviceUrls.js:7-8` points at
`http://localhost:8002/api/v1`; the gateway is GraphQL-only and does not proxy this endpoint.
So this is a cross-origin request, and `transaction-service/app/main.py:30-36` sets
`allow_headers=["*"]` but no `expose_headers` — a response *header* would be silently
unreadable by `fetch` in the browser until CORS was changed. `allow_headers` governs the
request; `expose_headers` governs the response, and only the former is configured.

**The blast radius is two callers, both in-tree.** `analytics-service/app/tools/backfill.py:126-179`
pages the endpoint expecting a bare list, and the frontend's `fetchTransactions`
(`api/transactions.jsx:24-31`) does `results.map(...)`. No other service calls it
(`account-service/app/config.py:76` defines the URL but has no call site). There is no
external consumer and no published API contract, so versioning would be ceremony over two
files.

That asymmetry is the actual crux, and it cuts against the envelope: a header is
non-breaking, an envelope is not. The decision below is that two in-tree edits are a smaller
long-term cost than a second way of saying "list plus total" in the same frontend.

## Alternatives considered

- **`X-Total-Count` response header** — rejected, though it is the only genuinely
  non-breaking option and that was weighed seriously. Three costs: it needs
  `expose_headers=["X-Total-Count"]` added to CORS for a direct browser client, which would be
  the repo's first use and a new way for a deploy to be subtly wrong (the total silently
  reads as absent, not as an error); `crudFactory.fetchAll` returns `response.json()` and
  discards the `Response` (`crudFactory.jsx:28`), so a header total requires changing the
  shared factory or bypassing it — i.e. it does *not* avoid a frontend change, it just moves
  it somewhere with a wider blast radius than the one file that owns this endpoint; and it
  would leave the transactions page reading a total from a header for the list and from a
  body field for the search, two mechanisms for one concept on one screen. Non-breaking today,
  more expensive to hold.
- **A separate `GET /transactions/count` endpoint** — rejected. There is precedent
  (`notification-service` pairs a bare list with `/api/v1/notifications/unread-count`), but it
  is precedent for a genuinely independent number — the badge count is not the count of the
  list you are reading. Here the total is *of this page's filter set*, so splitting it means
  two requests that can disagree (different transactions, different snapshots, filters
  duplicated in two query strings and drifting the first time one is added), plus a second
  round trip on the product's most-read screen to answer a question the first query already
  knows the answer to.
- **Opt-in envelope, `?include_total=true`** — rejected. Backwards compatible, and that is
  its only merit. The endpoint would have two return types, so `response_model` becomes a
  union, OpenAPI and the generated docs stop describing one thing, and every future reader has
  to determine which shape is live. It pays permanent structural complexity to avoid editing
  one 20-line loop and one 3-line mapping function.
- **`&limit=10000` from the client** — rejected, on the reasoning already recorded for
  [P1-13](2026-07-25-budget-spend-from-analytics.md): *"Trades a silent wrong answer for a
  silent ceiling that reappears at a different account size […] Cheapest to write, most
  expensive to trust."* It is additionally not even available here: `TransactionFiltersDTO`'s
  `le=200` (`dto.py:84`) caps the ceiling at 200, so the shortcut buys four times the current
  limit and nothing more. And it would not answer the actual question — with no total the UI
  still cannot distinguish "that is all there was" from "that is all you were given", which is
  the whole defect.
- **Cursor/keyset pagination instead of offset** — not seriously considered for this fix.
  `(date DESC, id DESC)` is already a stable total order, so a keyset cursor would be
  well-defined and would avoid OFFSET's deep-page cost. But it cannot express "page 5 of 12",
  and an explicit total with numbered position is precisely what the finding says is missing.
  Revisit only if row counts reach the scale where OFFSET hurts; at 93 rows per user-month
  that is not a real force.

## Consequences

**`total_count` becomes a claim the count query has to keep honest, so the filter predicates
must be shared.** The failure mode this decision introduces is not a missing total but a
*wrong* one: a count computed with a different filter set than the rows would put an
authoritative-looking number above rows that cannot add up to it — the exact shape of the
defect P1-14 is fixing, reintroduced one layer down. So the seven filter branches move into
one `_filter_clauses` helper that both queries call, and it returns *predicates*, not a
`Select`, so the count path cannot inherit the row path's `order_by`/`offset`/`limit`. The
outbound port's `count_filtered` deliberately has **no** `skip`/`limit` parameters: the
signature is where "the total ignores the page" is impossible to misread. The residual risk is
that someone later adds a filter to one path only, or adds pagination to the helper — the
structural defences are the port signature and two mutation checks in the plan, and this
paragraph exists so a future filter addition does not quietly reintroduce the class.

**`total_count` and `items` can disagree by one row, and that is accepted.** They are read in
the same `async with self._uow` block, so the same transaction — but under READ COMMITTED each
statement takes its own snapshot, so a concurrent insert can yield `total_count = 94` beside a
page computed from the earlier snapshot. The cost is a momentarily stale number in "viser 50
af 94"; no row is duplicated or lost. OFFSET paging over a date-descending order already has
that property under concurrent writes, and `REPEATABLE READ` on a read endpoint is
disproportionate to a transiently-off count. Noted in a comment at the call site rather than
fixed.

**Every list request now costs an extra `COUNT(*)`.** Index-served via
`ix_transactions_user_id` and `ix_transactions_dedup_key` (migration 011, which covers the
common account+period filter). At measured cardinality — 93 rows for the largest
user-month — it is noise. If it ever stops being noise, the answer is `count(*) OVER ()` in
the same statement, not a cache; deliberately not done now, because one shared filter
definition is worth more than one saved round trip.

**The frontend carries a temporary shape-tolerant reader, and it is load-bearing rather than
defensive.** Because the browser calls transaction-service directly, the naive rollout order
(server first) has a window in which an old bundle does `results.map(...)` on an object and
blanks the page. So `fetchTransactions` gains an `Array.isArray` branch and ships *before* the
server change; since the old server already honours `skip`/`limit`, pagination works
end-to-end in that window with `items.length` standing in for the total. This buys a real
property — every commit independently deployable, and the breaking commit revertable alone —
at the price of one branch that must be deliberately removed later. A dual shape on the
*server* was the alternative and is worse: it would need a second breaking change to retire,
and it hides "the envelope is not deployed yet" behind working-looking behaviour. The removal
is filed rather than left to memory, and its test asserts the branch's behaviour so deleting
it turns a test red instead of changing behaviour silently.

**The two read paths converge on one page size, so search drops from 100 to 50.** The list
and the search feed one pager, and shared page state is only coherent if "page 2" means the
same row range in both modes — otherwise the pager text flips between "Viser 1–50 af 93" and
"Viser 1–100 af 400" in the same widget on the same screen. 50 was already the REST default,
the gateway resolver default and `useNotificationFeed`'s size, so search is the outlier being
brought into line. Consequence: a search that used to surface 100 hits at once now shows 50 —
strictly better, since the remaining ones are now reachable instead of unreachable.

**`GET /api/v1/planned-transactions/` deliberately keeps its bare-array shape**, so the
service now has two list endpoints with two shapes. Accepted as the lesser inconsistency: that
endpoint takes no `skip`/`limit` at all, so there is no ceiling to remove — enveloping it would
churn a shape and break a frontend path for zero measured defect. The rule this establishes is
that the envelope belongs to *paginated* endpoints, not to lists in general, which is also how
analytics uses it.

**Unblocks** an honest pager, and with it the reconciliation P1-13 made possible but could not
deliver: after this the dashboard's 16 739,83 for June sits above 93 rows the user can
actually reach and add up, instead of above 50 that cannot sum to it. It also removes the last
consumer of the assumption that a bare list from this endpoint is complete, which is what let
the same 50-row ceiling bite twice in two services.
