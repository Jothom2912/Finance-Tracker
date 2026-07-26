---
title: P1-14 — the transactions page pages the whole period, with an honest total
date: 2026-07-26
status: in-progress
backlog-items: [P1-14]
related:
  - ../findings/2026-07-26-transaction-list-truncated-at-50.md
  - ../decisions/2026-07-26-transaction-list-envelope.md
  - ../findings/2026-07-25-budget-spend-truncated-at-50.md
  - ../plans/2026-07-25-p113-budget-spend-from-analytics.md
---

# P1-14 — the transactions page pages the whole period, with an honest total

## Goal

The transactions page stops presenting an incomplete set of financial records as if it were
complete: every row in the selected period is reachable, and the page states how many rows
it is showing of how many.

Done when: June 2026 for account 1 is reachable in full — 93 rows across pages — the pager
reads "Viser 1–50 af 93" on page one and "Viser 51–93 af 93" on page two, and the sum of the
listed amounts reconciles with the **16 739,83** analytics reports for the same period.
Proven by re-running the finding's measurement against the API *and* by driving the UI.

## Context

[The finding](../findings/2026-07-26-transaction-list-truncated-at-50.md) —
`fetchTransactions` (`services/frontend/src/api/transactions.jsx:24-31`) sends no `limit`,
transaction-service defaults to `limit=50` (`rest_api.py:61`) and the repository applies it
in SQL *after* `ORDER BY date DESC, id DESC`
(`postgres_transaction_repository.py:91`), so what disappears is the **oldest part of the
selected period**. Pick June and you see June 30 back to roughly June 16. The UI renders the
returned array into a `<table>` with no pagination, no total and no truncation notice
(`TransactionsList.jsx:80`), so nothing distinguishes this from "that is all there was".

Measured 2026-07-26 (user 1, account 1): June = 93 rows in Postgres against 50 shown →
**46% hidden**. July 61 → 11 hidden. April sits on exactly 50, one row from starting to lose
data with no visible change in behaviour.

This is the same defect mechanism as
[P1-13](../findings/2026-07-25-budget-spend-truncated-at-50.md), on the surface the user
actually reads — and it is *worse* after P1-13 than before. Since 2026-07-25 the dashboard
reads spend from analytics and reports June correctly as 16 739,83 across 93 transactions,
while the list shows 50 of them. The user now sees a **correct total that cannot be
reconciled against the rows underneath it**, and the natural reading is that the total is
wrong — the opposite of the trust P1-13 bought.

The response-shape question this forces is recorded separately in
[the decision note](../decisions/2026-07-26-transaction-list-envelope.md).

## Non-goals

- **`GET /api/v1/planned-transactions/` stays a bare array** (`rest_api.py:162-168`). It
  takes no `skip`/`limit` at all, so there is no ceiling to remove — only a shape to churn,
  and a frontend path to break, for zero measured defect.
- **No virtualisation.** It stays in P3-06; only that row's *pagination* clause moves out.
  Virtualisation matters once a single page is large, which 50 rows is not.
- **The `Field` bounds on `TransactionFiltersDTO` stay, including `le=200`**
  (`dto.py:77-84`). They guard construction outside the HTTP layer and are pinned by
  `test_dto_validation.py:114-135`. The duplication against the new `Query(...)` bounds is
  layered validation, not drift — noted in a comment so nobody "de-duplicates" it away.
- **The `seen_ids` guard in analytics' backfill stays** (step 11). `total_count` can only
  ever be an additional stop, never the only one.
- **No page in the URL.** The filters are `useState` (`TransactionsPage.jsx:36-44`), so a
  `?page=3` on its own would be a shareable link to page 3 of *somebody else's* filter set.
  Deep-linking requires putting the filters in the URL too — separate work.
- **No auth change, no role concept, no gateway change.** The browser talks to
  transaction-service directly (`serviceUrls.js:7-8`); the gateway is GraphQL-only and does
  not proxy this endpoint. The search path needs only an `$offset` the resolver already
  accepts.
- **No aggregation moves.** Unlike P1-13 this plan does not change where any number is
  computed; the page keeps reading the write side for rows and analytics keeps owning spend.
- **The list stays user-scoped, and the two read paths keep different scopes.**
  `fetchTransactions` sends no `account_id` at all (`api/transactions.jsx:24-31`) and
  `useTransactions:11` only puts `accountId` in the *query key*, so the REST list covers every
  account the user owns; the search path goes through the gateway, which requires
  `X-Account-ID` (`graphql_api.py:235-239`) and is therefore account-scoped. One pager will sit
  above two differently-scoped populations. Not a defect today — user 1 has exactly one account,
  and June is 93 rows both user-scoped and for account 1, so this plan's measurement is reachable
  as written — but for a multi-account user "af 93" and "93 resultater" would count different
  sets. Aligning them is its own decision (which scope is right for the list?) and is filed as
  P3-35, not smuggled into a pagination fix. Worth noting that the coherence argument the
  decision note makes for unifying `PAGE_SIZE` applies with more force to scope than to page
  size; it is deferred deliberately, not overlooked.

## Design decisions to record

Three, of which one is the decision note and two are local enough to live here.

**1. Response shape — envelope, recorded in
[decisions/2026-07-26-transaction-list-envelope.md](../decisions/2026-07-26-transaction-list-envelope.md).**

**2. `page` is a separate argument, not a member of `filters`.** Three reasons, by weight:
`filters` is about to be passed to *two* hooks (that is the step-9 bug fix), so a REST page
index inside it would churn the search cache key and GraphQL variables on REST page changes
and vice versa; the hook composes `{...filters, skip, limit}`, which is only clean while
`filters` is purely semantic — *which subset*, not *which window*; and "page resets when
filters change" is a statement about **two** pieces of state, so with page inside `filters`
the invariant is inexpressible and untestable.

**3. The frontend's tolerant reader lands before the breaking change.** The obvious order —
backend first, "same push" as the mitigation — leaves a window in which an old frontend hits
the new endpoint and `results.map is not a function` blanks the page. The reverse order has
**no** window: the frontend reader tolerates both shapes, and the old server *already*
honours `skip`/`limit`, so steps 5–9 deliver working pagination before the envelope exists.
Only the total is approximate in that window (`items.length`, i.e. "Viser 1–50 af 50") —
less than the truth, but more than today, where nothing is stated at all. Every commit is
independently green **and** independently deployable, and step 10 can be reverted alone
without breaking the client.

## Steps

Following P1-13's sequence (`9145333d` → `14a6fee2`): docs first, new code unwired, then the
flip, old path last.

1. [x] `docs(dev-notes): plan for P1-14 — paginering af transaktionslisten` — this file,
       `00-INDEX.md`.
2. [x] `docs(dev-notes): beslutning — total_count-envelope på transaktionslisten` — new
       `decisions/2026-07-26-transaction-list-envelope.md`, `00-INDEX.md`,
       `backlog/BACKLOG.md` (P1-14 → `in-progress`, link plan + decision).
3. [x] `test(transaction): REST-lag-tests for transaktionslisten` — new
       `services/transaction-service/tests/integration/test_transaction_list_api.py`,
       asserting the **current** bare-list contract. The service has **zero** tests on its
       HTTP boundary today, so its most-read endpoint has never been exercised through the
       app; this file lands first so step 10 becomes a visible assertion flip instead of a
       leap. Fixtures copied from `test_transaction_repository_filters.py` (module-scoped
       `PostgresContainer("postgres:16")` + `_migrated_db` running `alembic upgrade head`),
       plus a per-test fixture that opens one session, seeds through
       `PostgresTransactionRepository` without committing, overrides
       `app.dependency_overrides[get_db]` to yield that same session, and drives
       `httpx.AsyncClient(transport=ASGITransport(app=app))`; rollback on close = clean slate
       per test. Two deliberate deviations from `notification-service`'s template: **real
       Postgres, not `sqlite+aiosqlite`**, because the assertions are about `COUNT` versus
       `OFFSET/LIMIT` after `ORDER BY date DESC, id DESC` and that is precisely where sqlite
       is allowed to differ; and **seed through the repository, not `POST /transactions/`**,
       because `get_transaction_service` injects a real `CategorizationClient` and a POST per
       row would fire an HTTP call with a live timeout. Auth via
       `jose.jwt.encode({"user_id": uid}, settings.JWT_SECRET, ...)` — `decode_token` accepts
       `user_id` or `sub` and `require_exp` defaults `False` (per the P2-02 correction), so no
       `exp` is needed. **Seed more than one page**, or mutation check 3 cannot fail.
       ~150 new lines, no production code touched.
4. [x] `fix(transaction): Query-bounds på skip/limit — 422 i stedet for 500` —
       `rest_api.py:51-72`, `skip: int = Query(default=0, ge=0)` and
       `limit: int = Query(default=50, ge=1, le=200)`, matching
       `analytics-service/app/adapters/inbound/rest_api.py:103-134`. Today `?limit=201`
       reaches `TransactionFiltersDTO(...)` inside the handler body and raises
       `pydantic.ValidationError` where FastAPI can no longer translate it, so a pure input
       error surfaces as 500. Precisely: a bare annotation *is* type-validated by FastAPI
       (`?limit=abc` already 422s), but it carries no bounds — `ge`/`le` require `Query(...)`,
       and without them the only bounds check is the DTO's, one layer too deep to be
       translated. Measured against the running service 2026-07-26: `?limit=201`, `?limit=0`
       and `?skip=-1` all return **500**, `?limit=200` returns 200 OK with 200 rows (so
       backfill's `PAGE_SIZE = 200` sits exactly on the new `le` bound, with no margin).
       Its own step: separate defect, separate rollback, and bundling a
       status-code change into a shape change would make neither bisectable. +3 cases in
       step 3's file (`?limit=201`, `?limit=0`, `?skip=-1` → 422). ~4 lines.
5. [x] `feat(transaction): count_filtered + delt filterklausul i transaktions-repoet` —
       `app/application/ports/outbound.py` (+`count_filtered`, same filter params **minus**
       `skip`/`limit` — the omission *is* the contract),
       `postgres_transaction_repository.py` (extract `_filter_clauses`, add
       `count_filtered`), `tests/integration/test_transaction_repository_filters.py` (+3
       tests). **Nothing calls it yet**; `find_filtered` behaves identically and all five
       existing filter tests stay byte-identical. A predicate list, not
       `_apply_filters(stmt, …)`: a helper that takes and returns a `Select` invites
       `_apply_filters(count_stmt, …).order_by(...)` and lets the count path inherit the row
       path's clauses, which the list form cannot express.
       `select(func.count()).select_from(...)` is the shape from
       `notification-service/app/adapters/outbound/postgres_notification_repository.py:71-81`;
       index-served via `ix_transactions_user_id` and `ix_transactions_dedup_key`
       (migration 011). ~+55/−10.
6. [x] `feat(frontend): pak transaktions-envelope ud og send skip/limit` — new
       `src/lib/pagination.js` (`PAGE_SIZE = 50`, `pageCountOf` flooring at 1),
       `src/api/transactions.jsx`, new `src/api/transactions.test.jsx`. **No change to
       `crudFactory.jsx`**: the premise that `fetchAll` is unusable holds only for a
       *header*-based total — it returns `response.json()` verbatim (`crudFactory.jsx:28`)
       and the total is in the body, so the envelope flows through untouched and the only
       broken line is `results.map(...)` at `transactions.jsx:30`. A `fetchAllWithMeta` would
       encode *one* endpoint's contract into a module shared by five resources without it
       (two of them raw `export const fetchX = crud.fetchAll` re-exports), and the
       `uploadTransactionsCsv` bypass precedent exists because *that* call needs a different
       HTTP shape (multipart), not a different body shape. `params.skip` is set
       unconditionally — `if (skip)` would drop `skip=0`, the common case. Includes the
       `Array.isArray` transition branch (see step 11's note and the spawned follow-up).
       **Page size unified at 50** for both read paths: search hardcodes 100
       (`useTransactionSearch.jsx:58`) while the REST default and the gateway resolver
       default are both 50; shared page state is only coherent if "page 2" means the same row
       range in both modes, or the pager text flips between "1–50 af 93" and "1–100 af 400"
       in the same widget. ~+30/−3 plus ~70 test lines.
       **Done in `74e3f8ea`**, with two deviations, both additive: `pagination.test.jsx`
       (7 cases) because `pageCountOf`'s floor-at-1 is what step 9's clamp rests on and
       untested domain logic is not accepted here; and the follow-up **filed as P3-36 in the
       same commit**, because the code comment names it and a comment pointing at a
       non-existent backlog line is broken at HEAD — the decision note already claimed the
       removal was "filed rather than left to memory", and it was not. Both mutation checks
       bite: `if (skip)` → the two `skip=0` cases fail; deleting the `Array.isArray` branch →
       the three transition cases fail. **HEAD between step 6 and step 7 renders a broken
       transactions page** — `useTransactions` still does `query.data ?? []`, so
       `TransactionsList` gets an object and `.map` throws. Green (all mocks are at the API
       boundary) but not runnable; step 7 is the repair, and this is what the risk section
       means by the frontend stack reverting as a range rather than per commit.
7. [x] `feat(frontend): useTransactions tager side og returnerer totalCount` —
       `src/hooks/useTransactions.jsx`, `src/hooks/useTransactions.test.jsx`. Signature
       `useTransactions(filters, page = 1)`; `transactionsQueryKey(accountId, filters, page)`;
       `placeholderData: keepPreviousData` (the pattern already at
       `useTransactionSearch.jsx:63`); returns `totalCount: query.data?.totalCount ?? null`
       — `null` not `0`, because `0` means "empty period" and would let step 8's clamp fire on
       a guess — and exposes `isPaging: query.isPlaceholderData`. Raw `isFetching` is
       deliberately **not** exposed: `isPlaceholderData` is true precisely while an older
       page's rows are on screen under a new key, whereas `isFetching` is also true during a
       post-mutation background refetch where a dim would be noise. Prefix invalidation
       (`invalidateFinancialData.js:21-27`) is unaffected by the extra key member. ~+15/−8
       plus ~10 test sites updated.
       **Done in `c89f594e`** (20 tests, up from 9), which also **repairs HEAD** — the page
       gets an array again. One addition beyond the plan: a test that pins
       `isPlaceholderData` *against* `isFetching` by driving a post-mutation background
       refetch, since every other paging assertion passes under either. Mutation checks, one
       at a time: drop `page` from the key → 5 fail; `page * PAGE_SIZE` → 5 fail; `?? 0`
       instead of `?? null` → the 2 null cases fail; `isFetching` → exactly the new refetch
       test fails. Still **unverified in a browser**: the api-layer tests mock `apiClient` and
       the hook tests mock the api module, so the two halves are never composed against a real
       response. The live drive belongs in step 9, where there is a pager to observe; the
       server side of it (`skip`/`limit` honoured, `limit=200` → 200 rows) was already measured
       against the running service in step 4.
8. [x] `feat(frontend): Pagination-komponent med "Viser 1–50 af 93"` — new
       `src/components/Pagination/{Pagination.jsx,Pagination.css,Pagination.test.jsx}`.
       Unused this step; the test proves it standalone, so the step is trivially green.
       Folder-per-component with its own CSS is the convention (there is no shared component
       library); `:root` tokens from `index.css:11-92` only, modelled on `.budget-toggle-btn`
       (`BudgetProgressSection.css:175-193`); focus ring comes free from `index.css:121`.
       a11y: the count line renders **even when `pageCount === 1`** ("Viser 1–37 af 37
       transaktioner" is the antidote to exactly the doubt this plan is about) and only the
       buttons hide; `role="status" aria-live="polite"` on a `<p>` that stays mounted while
       `totalCount > 0` so only its text mutates and it announces once per page change
       instead of twice; `aria-label="Forrige side"` **contains** the visible "Forrige" to
       satisfy WCAG 2.5.3 (Label in Name); real `disabled` at the edges, not `aria-disabled`
       (accepted cost: clicking to the last page disables the focused button and drops focus
       to `<body>` — the `role="status"` announcement is the compensating feedback, and the
       repo has no `aria-disabled` precedent); buttons are **not** disabled while fetching,
       because rapid next-next is legitimate and `keepPreviousData` handles the overlap.
       ~120 new lines + ~60 test lines.
       **Done in `8e641822`** (19 tests). Two decisions firmed up while writing it. The
       component takes **no `isPaging`/`isFetching` prop at all** — "buttons are not disabled
       while fetching" is stronger as an absent parameter than as an unused one, and the dim
       belongs on the table in step 9. And `pageCount` is **computed** from `totalCount` via
       `pageCountOf` rather than passed in, so the pager and step 9's clamp cannot disagree
       about how many pages exist. Beyond the plan: two tests assert the live region is the
       **same DOM node** across a page change and across the buttons disappearing, which is
       the only way the announce-once property can fail (moving the `<p>` inside
       `pageCount > 1 && …` compiles, renders and looks right). Mutation checks: that move →
       3 fail; rendering at `totalCount === 0` → 1; unclamped `lastRow` → 3; an `aria-label`
       that drops the visible word → 6; `aria-disabled` for `disabled` → 1.
9. [x] `feat(frontend): server-side paging på transaktionslisten` —
       `src/pages/TransactionsPage.jsx`, `TransactionsPage.css`, new
       `src/pages/TransactionsPage.test.jsx`. Page reset via **set-state-during-render**, not
       a `useEffect`: with an effect the render *preceding* it already has the new filters and
       the stale page, so a request with `skip=100` against a freshly filtered set is issued
       and briefly rendered before the reset lands. A `resultsKey` string over the three
       filter controls plus the debounced search term covers `FilterComponent`'s date presets
       automatically and will cover a fourth filter added later, which wrapping the three
       setters individually would silently miss. Clamp
       `if (pageCount != null && page > pageCount) setPage(pageCount)` handles the total
       shrinking below the current offset (delete the last row on page 2): guarded on the
       server having answered, converges in one step because `pageCountOf` floors at 1, and
       deliberately not attempted in the mutation's `onSuccess`, where the client cannot know
       the new total before the refetch lands. `setPage(1)` also on save and after a
       successful CSV import, so a new row is actually on screen. Page changes **dim** the
       stale table (`opacity: .55`, `aria-busy`) rather than replacing it with a spinner,
       which would collapse the page height and scroll-jump the user; `prefers-reduced-motion`
       in `index.css:127+` already neutralises the transition globally. The empty state cannot
       lie, in three layers: the clamp makes `items.length === 0 && totalCount > 0`
       unreachable, `Pagination` returns `null` at `totalCount === 0` so a genuinely empty
       period gets no "Side 1 af 1" beside the empty-state card, and `TransactionsList` gains
       `emptyMessage`/`showEmptyAction` (defaulting to today's string, so no caller breaks) so
       a zero-hit search stops saying "for de valgte **filtre**" with a "Tilføj din første
       transaktion" CTA. ~+45/−15 plus ~120 test lines.
       **Done in `7f86c86f`** (15 page tests, the page's first coverage). Three things the
       plan did not anticipate. **(a) The search deliberately gets no pager in this step** —
       `useTransactionSearch` cannot page until step 10, and a pager whose buttons do nothing
       is worse than none, so `activeTotalCount` is `isSearchActive ? null : totalCount` and
       step 10 makes it symmetric. **(b) The first clamp test was a false positive**: it shrank
       the total by changing a date filter, which resets the page via `resultsKey`, so it was
       green with the clamp deleted. It now shrinks the total across a bare `rerender` with
       filters untouched, leaving the clamp as the only mechanism that can move the page. A
       second case pins one-step convergence (page 5 → 2, never 4, 3). **(c) `userEvent` was
       new to this repo** and is not act-wrapped by RTL 14, so every stateful interaction
       printed "not wrapped in act". Switched to `fireEvent` (the existing convention) in both
       new test files — `ced0ddce`. Mutation checks: remove the clamp → the 2 clamp tests fail;
       drop its `!= null` guard → 2 fail; remove the reset → the 3 reset tests fail; and
       **replace the render-phase reset with a `useEffect` → only the "sender ALDRIG et request
       med nye filtre og gammelt sidetal" test fails**, catching the exact offending call
       (`startDate=2026-05-01` with `page=5`) while both "resets to page 1" tests stay green.
       That last pair is the plan's central claim, now demonstrated rather than argued.
       `npm run build` is clean. **Still not driven in a browser** — the repo has no Playwright
       or Puppeteer and its e2e suite is API-level, so a real UI drive needs a human at
       `npm run dev`; noted under Verification.
10. [x] `fix(frontend): søgning respekterer aktive filtre og kan pages` —
       `src/hooks/useTransactionSearch.jsx`, its test, `TransactionsPage.jsx`. `$offset: Int!`
       added to the document — the only thing missing, since the resolver already takes it
       (`gateway-service/.../graphql_api.py:497-523`) — `limit: 100` → `PAGE_SIZE`, `page` in
       the query key (or the cache serves page 1 forever), `totalCount ?? null` and
       `isPaging`, symmetric with step 7. The reported bug is one line at
       `TransactionsPage.jsx:79`: `useTransactionSearch(debouncedSearchTerm, filters, page)`
       — the hook already accepts and forwards `filters` (`:54-57`) and already has them in
       its key (`:40`). **Page state is shared with the list**: the two result sets are
       mutually exclusive (`isSearchActive` switches heading and array at `:283-300`), there
       is one pager, and `debouncedSearchTerm` is in `resultsKey` so entering, changing or
       clearing a search resets to page 1; a separate `searchPage` would need its own reset
       rules and would resurrect a stale page number when the user retypes the same term.
       Accepted consequence: clearing the search lands on page 1 of the filtered list, not the
       page you were on before searching. Copy splits — the status line by the search box
       keeps only the *total* (`93 resultater for "netto"`) and the range moves into the pager,
       because today's `50 af 400 resultater` reports a truncation with no way to act on it;
       the status line gets the same `is-stale` dim, since with `keepPreviousData` it briefly
       shows the previous term's count beside the new term. **Behaviour change to flag:**
       because the default filter is the current month (`:36-43`), search now covers only that
       month. That is the correct fix — the filter panel was visually active and being ignored
       — but anyone used to searching all history will read it as a regression; global search
       belongs in an explicit "Søg i hele historikken" toggle, not here. ~+20/−8.
       **Done in `92ab86f0`** (335 tests, up from 319: +7 hook, +8 page). Three notes.
       **(a) `totalCount` flipped to `?? null` here too**, which the plan called "symmetric
       with step 7" without naming the consequence: the status line needs its own
       `searchTotalCount != null` guard, or an active search renders "null resultater" for one
       paint before the answer lands. **(b) `isPaging` had to be routed, not just returned** —
       `activeIsPaging = isSearchActive ? searchIsPaging : isPaging`, because the table's dim
       previously read the *list's* flag unconditionally, so a background list refetch would
       have dimmed search results (the other population) and a search page change would not
       have dimmed anything. Two tests pin both directions. **(c) The `$offset: Int!`
       declaration is pinned by asserting on `gqlRequest.mock.calls[0][0]`** — the document is
       the first argument, so it needs no export. Worth the seemingly tautological test because
       this is the one mutation a mocked suite otherwise cannot see: sending `offset` without
       declaring it fails *document validation* at the gateway, i.e. every search on every page
       fails hard, and nothing in a mocked test would notice. Mutation checks, each alone:
       `page` out of the search key → 3 fail; `limit: 100` → 2; `offset` dropped from the
       variables → 3; `$offset: Int!` removed from the document → 1; `?? 0` → 1; `filters` not
       forwarded → 1; `page` not forwarded → 3; `activeTotalCount = totalCount` → 2;
       `activeIsPaging = isPaging` → 2; the interval back in the status line → 1; the null-guard
       removed → 1. `npm run build` and `eslint src` clean. **Not driven in a browser** — same
       constraint as step 9, and the scope change (search now covers the active date range) is
       exactly the kind of thing a human should see once; noted under Verification.
11. [ ] `feat(transaction)!: total_count-envelope på GET /api/v1/transactions/` — the risky
       step. `app/application/dto.py` (+`TransactionListResultDTO`),
       `ports/inbound.py:27`, `service.py:163-175`, `rest_api.py:51-72`,
       `tests/unit/test_transaction_service.py:293-364`,
       `tests/integration/test_transaction_list_api.py` (flip to envelope),
       `tests/e2e/test_transaction_flow.py:258-259`. Rows first, count second, both inside the
       **same** `async with self._uow` — same DB transaction. A **DTO, not a tuple**, across
       the inbound port: `gateway-service/app/application/ports/outbound.py:86-97` returns
       `tuple[int, list[...]]` correctly for *its* situation, a driven/outbound port whose
       tuple is internal transport between an HTTP adapter and a resolver that immediately
       repacks it, and gateway does not own the envelope DTO. `ITransactionService` is the
       opposite: a driving/inbound port whose return value **is** the response body. FastAPI
       needs a `BaseModel` for `response_model`, OpenAPI and the frontend contract; a tuple
       would force `rest_api.py` to unpack and construct the DTO in the adapter — putting the
       response shape in the adapter for an endpoint whose whole point is the response shape —
       and make `total_count`/`items` positional, where a reversed unpack reads fine and
       type-checks. The analytics precedent is exact: its query service returns
       `TransactionSearchResultDTO`, its router declares it as `response_model`. The
       repository correspondingly gains **two methods** rather than
       `find_filtered -> tuple[int, list[Transaction]]`, which would force a COUNT on every
       caller and rewrite all five repo integration tests plus all three service unit tests
       in the same commit as the shape change. The e2e edit must be in this commit:
       `len({"total_count": …, "items": …}) >= 3` is `2 >= 3`, a **failing** assertion, so
       omitting it leaves the e2e suite red. ~+35/−15 plus test updates.
12. [ ] `fix(analytics): backfill læser envelope-formen fra transaktionslisten` —
       `services/analytics-service/app/tools/backfill.py:127-180`, its test at `:99-105` and
       `:190-201`. Reads `body["items"]` and `body["total_count"]`, plus
       `if len(seen_ids) >= total: break` after the existing short-page break, plus a note
       that `PAGE_SIZE` (200) must stay `<=` the endpoint's `le` bound or every page 422s.
       **The `seen_ids` guard stays**: `total_count` does not bound the loop, because a source
       that repeats a page will happily also report a plausible total, and the total can
       *grow* while we page (live imports), so it can only be an extra stop — never an assert
       and never the sole condition. It also produces the per-account count in the closing log
       line. The stale comment at `:144-149` gets **rewritten**: it names `find_by_account`,
       and `grep -rn find_by_account --include=*.py services/` now hits only two comments —
       the method is gone, so the guard's stated rationale no longer matches reality even
       though the guard is still right. Critically,
       `test_terminates_when_source_ignores_pagination` (`:187`) must return a total far ahead
       (`len(full_page) * 10`) so both the short-page condition and the total condition are
       out of play and it is still the `seen_ids` guard that stops the loop — otherwise that
       test stops proving anything. ~+12/−8.
13. [ ] `docs(dev-notes): P1-14 close-out` — `services/transaction-service/README.md` (the
       list returns an envelope; `skip`/`limit` 422 out of range), the finding
       (`status: resolved` + `resolved-by`), `BACKLOG.md` (P1-14 → `done 2026-07-26` with the
       measurement; P3-06's pagination clause trimmed to virtualisation only), the decision
       note (`status: implemented`), a session log, and one `00-INDEX.md` line per new file.
14. [ ] **Verification** — see below.

## Verification

Per step, before committing. Note that `check | tail && commit` hides the exit code (it has
happened twice) — run the check as its own call and read the code:

```
make -C services/transaction-service test        # unit + integration, two invocations
cd services/frontend && npm test                 # vitest run
make lint-repo                                   # ruff over services scripts tests
```

After steps 11–12, against the running stack:

```
make ci-status                                   # is master green
docker compose build transaction-service && docker compose up -d transaction-service
make test-e2e                                    # requires the stack up
```

**The measurement** — the finding's numbers are the contract. With a token for user 1:

```
GET /api/v1/transactions/?account_id=1&start_date=2026-06-01&end_date=2026-06-30&limit=50
→ total_count: 93, len(items) == 50
July  → total_count: 61
April → total_count: 50 with 50 items    # "one row from silent loss" now reads as 50 of 50
```

reconciled against `select count(*) from transactions where user_id=1 and account_id=1 and
date between …` in Postgres.

**The UI drive cannot be automated in this repo** — there is no Playwright or Puppeteer in
`services/frontend/package.json` and `tests/e2e/` talks to the API, not a browser. So the
checks below are a human at `npm run dev`, and any claim that they passed must come from
someone who actually looked. Note also that until step 11 the total is `items.length`, so
the pager reads "Viser 1–50 af 50" for June: pageability is verifiable now, the *number* is
not.

**From the UI**, which is what the finding actually demands: select June 2026 on account 1,
page through, count 93 rows, and reconcile the sum of the listed amounts against the
**16 739,83** analytics reports for the period. Also confirm the pager reads "Viser 1–50 af
93" then "Viser 51–93 af 93", that a date preset resets to page 1, and that a search now
respects the active date range.

**Mutation checks** — a reviewer should watch each of these fail the right tests:

1. Delete one `if … is not None` branch from `_filter_clauses` → repo
   `test_count_honours_every_filter` **and** the filtered REST case must fail. (Proves the
   sharing is load-bearing, not cosmetic.)
2. Give `count_filtered` `.offset(skip).limit(limit)` → `test_count_ignores_pagination` and
   the skip case must fail.
3. `total_count=len(results)` in the service → the REST limit and skip cases must fail.
   (Only fails if step 3 seeded more than one page — hence that requirement.)
4. Forward `skip`/`limit` into `count_filtered` → the new service unit test must fail.
5. Flip `order_by` to `date.asc()` → `test_same_date_rows_order_by_id_desc` and the
   newest-first case must fail.
6. Revert `Query(...)` to bare annotations → the three 422 cases must go back to 500.
7. Revert the backfill to `.json()` as a list → `test_backfill` must fail **loudly**
   (`TypeError`), never silently backfill zero rows.
8. `if (skip)` instead of the unconditional `params.skip` → the `skip: 0` case in
   `transactions.test.jsx` must fail.

## Risks & rollback

**Deploy skew is eliminated by the ordering**, not mitigated by a shim. The frontend's
tolerant reader lands in step 6, long before step 11. In that window pagination works (the
old server honours `skip`/`limit`) with an approximate total (`items.length`) — less than the
truth, more than today. A dual shape on the server was rejected instead: it would have to be
removed later by a *second* breaking change, and it hides "the envelope is not deployed yet"
behind working-looking behaviour.

**The gateway must not be older than the code — verified 2026-07-26, cleared.** `$offset` needs
the resolver argument to exist. It does on master (`graphql_api.py:505`), but GraphQL validates
the *document* — if the running gateway predated it, search would fail **hard** for every query
on every page, with no partial degradation and no client-side workaround (omitting `offset` from
the variables does not help; the declaration is what is validated). Checked against the
**running** container (not master, per the image-staleness lesson) by schema introspection:
`searchTransactions(query: String!, startDate: Date, endDate: Date, categoryId: Int,
txType: String, limit: Int!, offset: Int!)`. Note the type: `offset` is **`Int!`**, so step 10's
document must declare `$offset: Int!` and must always send a value — `offset: null` fails
validation rather than falling back to the resolver default.

**`total_count` and `items` can disagree by a row.** Two statements in one transaction take
two snapshots under READ COMMITTED, so a concurrent insert can produce `total_count = 94`
beside a page computed from the earlier snapshot. Bounded to a momentarily stale number in
"viser 50 af 94"; no row is duplicated or lost, and OFFSET paging over a date-descending
order already has that property under concurrent writes. `REPEATABLE READ` on a list endpoint
is disproportionate. A comment in the service, not a fix.

**One extra `COUNT(*)` per list request.** Index-served; at measured cardinality (93 rows per
user-month) it is noise. If it ever matters the answer is `count(*) OVER ()` in the same
statement, not caching — explicitly not done now, because one shared filter definition is
worth more than one saved round trip.

**Backfill run against an un-updated service** raises `TypeError` on the first page:
immediate and loud. The tool is manual and `upsert_core` with `event_ts=0` is idempotent, so
a half-finished run leaves no bad ES state.

**Deep search offsets**: ES `from + size` is capped by `index.max_result_window` (10 000), so
roughly page 201 errors. Fails visibly through the existing `searchError` path. Backlog line,
not scope.

**The search scope change will read as a regression** to anyone used to searching all
history, even though filtered search is the correct behaviour. Called out in the close-out;
the filter panel sits directly above and communicates the scope.

**Rollback.** Every commit is independent. Step 11 reverts alone — `count_filtered` and
`_filter_clauses` stay behind, unused and harmless — *without* breaking the frontend,
precisely because it tolerates both shapes. The frontend stack reverts 10→9→8→7→6, or as one
range revert. There is no feature flag; a `PAGE_SIZE`-based kill switch would reintroduce the
`&limit=10000` shortcut this plan and P1-13's decision both reject, so it is not wired.

## Outcome (fill in when done)
