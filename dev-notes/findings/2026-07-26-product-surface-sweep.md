---
title: Product-surface sweep — user domain, security perimeter, UX maturity, build/ops hygiene
date: 2026-07-26
severity: HIGH
area: cross-cutting
status: open
backlog: [F2-08, F2-13, P1-15, P2-26, P2-27, P2-28, P2-29, P3-18, P3-24, P3-25, P3-26, P3-27, P3-28, P3-29, P3-30, P3-31, P3-32, P3-33, P3-34]
resolved-by: null
---

# Product-surface sweep 2026-07-26

Method: four parallel read-only reviews (user-service + auth surface; frontend UX/a11y;
security posture; performance & ops), each instructed to read
[backlog/BACKLOG.md](../backlog/BACKLOG.md) first and report only what is **not** already
tracked as P1-01…P3-23. Findings below were then re-verified by hand against source, and
where noted, against the running dev stack.

Two items were serious enough to get their own documents and are only summarised here:

- [2026-07-26-transaction-list-truncated-at-50.md](2026-07-26-transaction-list-truncated-at-50.md) → **P1-14**
- [2026-07-26-categorize-endpoint-unauthenticated.md](2026-07-26-categorize-endpoint-unauthenticated.md) → **P1-15**

IDs here use `SEC-*` / `UX-*` / `OPS-*` so they cannot be confused with the `C/H/M/L`
scheme owned by [2026-07-07-architecture-audit.md](2026-07-07-architecture-audit.md).

---

## 0 — The framing: there is no user domain

This is the sweep's main structural result, and it is the reason several unrelated-looking
gaps below keep pointing at the same hole.

`user-service` exposes **four endpoints** — register, login, `/me`, internal lookup
(`app/adapters/inbound/rest_api.py:31,43,55,67`). The `users` table has **five columns**
(id, username, email, password_hash, created_at) and has not been extended since migration
001. The repository has `create` and three `find_by_*` and **no write path to an existing
user at all** (`app/adapters/outbound/postgres_user_repository.py`). The inbound port
declares exactly three methods (`app/application/ports/inbound.py:11-18`).

Absent, verified by grep across all 12 services: change password, forgot/reset password,
change email, email verification, refresh token, server-side logout or revocation, account
deletion, data export, soft-delete/deactivation, roles, display name, locale, timezone,
currency preference, notification preferences.

The rest of the system is a mature financial platform — sagas, outbox, CQRS read store, a
categorisation feedback loop. The person using it cannot change their own password. Every
other bounded context got extracted and hardened; this one never got written.

Three consequences that are easy to miss:

1. **It is a security gap, not only a feature gap.** No password rotation, no revocation,
   no lockout (`SEC-4`), 60-minute tokens with no refresh, and a client-side-only logout
   (`AuthContext.jsx:51-56`) that leaves the token valid until `exp`.
2. **It is a GDPR gap.** The app processes PSD2 bank data and full transaction history for
   Danish users. There is no deletion, no export, no retention anywhere (`grep -i
   'gdpr|export|retention|anonymi'` → zero real hits). Art. 15/17/20 are not optional the
   moment a second person uses this.
3. **Deletion is genuinely hard here, and that is interesting rather than unfortunate.** A
   user's data is spread across account-, transaction-, budget-, goal-, categorization- and
   notification-service with no cross-service delete orchestration and no `UserDeletedEvent`
   in the contracts (`shared/contracts/contracts/events/user.py` contains only
   `UserCreatedEvent`). Database-per-service turns the right to erasure into a distributed
   transaction — which is precisely what saga-service exists for, and it is the one job
   nobody has given it.

**Design constraint for whoever picks this up**: `email` is carried in `UserCreatedEvent`
and minted as a JWT claim (`app/auth.py:28-34`). Changing an email therefore needs a
full-state `UserUpdatedEvent` on the self-healing-consumer pattern the conventions already
mandate. Ship "change email" without it and you have manufactured a silent read-model
desync of the same class as P3-20.

→ Feature backlog **F2-08** (profile + settings MVP), **F2-09** (password reset — gated on
the email decision in P3-18), **F2-10** (GDPR export + deletion saga).

---

## 1 — Security (`SEC-*`)

Everything here is outside the existing backlog. Overlaps are called out explicitly.

### SEC-1 — The shared HS256 secret is in cleartext in a public repo · CRITICAL

`k8s/secrets.yaml:8-10` is git-tracked and contains `JWT_SECRET`, `SECRET_KEY` and
`INTERNAL_API_KEY` as `dev-secret-key-change-in-production`. The same value appears ~33
times in `docker-compose.yml` (e.g. `:141, 832, 1067`). BACKLOG.md's own P1-08 note
confirms `origin` is public (verified 2026-07-26 by anonymous API read).

All 12 services share one symmetric key, so anyone who reads the repo can mint a valid
token for an arbitrary `user_id` against every service.

**This is not P2-15 and not P3-02.** P2-15 is about *how* k8s secrets should be managed
(SOPS/secretGenerator); P3-02 is about *moving to RS256 later*. Neither says the current
value is disclosed **now**. Rotation is ten minutes and is independent of both.

Related, same class: `INTERNAL_API_KEY` defaults to the well-known
`"dev-internal-api-key-change-in-production"` in three services
(`goal-service/app/config.py:13`, `banking-service/app/config.py:17`,
`notification-service/app/config.py:11`). user-service (`config.py:14` → `None`) and
account-service (`config.py:82`, no default) fail closed correctly — that is the model the
other three should copy.

### SEC-2 — `require_exp=False` in all 12 services · HIGH

`services/shared/auth/auth/fastapi.py:28` and `auth/jwt.py:27` default to `False`, and no
call site opts in — verified across all 12 `app/auth.py`. A token without an `exp` claim is
accepted and never expires.

Latent on its own, because user-service always sets `exp` (`app/auth.py:27-35`). Combined
with SEC-1 it is the difference between a leaked secret granting 60-minute tokens and it
granting permanent ones.

**P2-02 has `require_exp` in its title and is marked done.** The capability was built; the
flag was never turned on. One line per service. See §4.

### SEC-3 — The gateway is not a perimeter · HIGH (architectural)

`services/frontend/src/config/serviceUrls.js:2-31`: the browser talks directly to ports
8001–8010, i.e. ten origins. `docker-compose.yml` additionally publishes on the host: all
nine Postgres instances (5433–5441, with passwords like `transaction_service_pass` in the
same file), RabbitMQ 5672 + management UI 15672 on `guest:guest`, Elasticsearch 9200 with
`xpack.security.enabled: "false"`, Redis 6380 with no password, Ollama 11435. Docker
publishes on `0.0.0.0` by default, so this is LAN-reachable, not loopback-only.

> **Datastore-halvdelen lukket 2026-07-28** i `5ea37f0d` — de 14 datastore-mappings binder
> `127.0.0.1`. LAN-rækkevidden var **ikke teoretisk**: målt før fixet svarede alle 14 porte fra
> LAN-IP'en, ES gav `transactions_v2` 642 docs + `accounts_v1` 292 uden auth, og RabbitMQ-mgmt
> gav fuld admin på `guest:guest`. Efter: 0/14. **De ti browser-origins og ADR'en står stadig**,
> og credentials er urørte — angrebsfladen er flyttet fra "alle på LAN'et" til "alt på
> maskinen", ikke lukket.
> [Plan + Outcome](../plans/2026-07-28-p324-datastore-loopback-bind.md#outcome).

This is the root cause behind several separate symptoms and should be decided as one thing:

- there is no single place to add rate limiting (`SEC-4`), CSP, or a WAF;
- the JWT cannot move to an HttpOnly cookie (`SEC-6`) because there are ten origins;
- Swagger is open on all 12 services in every environment — none of the `app/main.py`
  files set `docs_url=None` (verified on all 12). P3-12 covers gating GraphiQL on the
  gateway only.

Not necessarily a bug — a demo/portfolio system may reasonably accept it. But it should be
an explicit decision with a written trade-off rather than an accident of compose defaults.
Removing the host port publishing for the datastores is the cheap half and has no downside.

### SEC-4 — No rate limiting anywhere · HIGH

Zero hits for `slowapi|limiter|rate_limit|limit_req` across `services/`, `nginx.conf` and
CI. `POST /api/v1/users/login` (`user-service/.../rest_api.py:43-52`) has no throttling, no
lockout, no backoff, no CAPTCHA. Password policy is length only — min 8, max 128
(`app/application/dto.py:10-11`), no complexity rule and no breach check.

Note the interaction with P2-11: moving bcrypt off the event loop was correct, but it also
removed the accidental CPU brake that was the only thing slowing an attacker down. And with
bcrypt(12) at ~250 ms per attempt, unauthenticated login is now also a cheap DoS vector.

One thing already right: login returns the same error for unknown user and wrong password
(`service.py:109,115`), so there is no enumeration there. `register` does leak existence
via 409 (`service.py:52,55`) — usually an acceptable trade for usability, worth being
deliberate about.

### SEC-5 — Any authenticated user can delete the global taxonomy · HIGH

`categorization-service/app/adapters/inbound/category_api.py:73-76` (`DELETE /categories/{id}`)
and `:132-135` (subcategories), plus create/update at `:45,63,97,122`. All take
`_user_id: int = Depends(get_current_user_id)` — the underscore is the finding: identity is
resolved and discarded. The taxonomy is global and shared by all users under ADR-003, so
one user's delete lands in every other user's categorisations, budget lines and analytics.

There is no role or admin concept anywhere in the codebase (`grep -E 'admin|role|is_admin'`
across categorization + user → nothing). So the fix requires a decision, not just a
dependency: introduce a minimal role on the user model, or make taxonomy mutations
internal-only and expose a curated subset. ADR-003 settled *ownership* of the taxonomy; it
did not address *authorisation* over it.

### SEC-6 — No security headers; JWT in `localStorage` · MEDIUM

`services/frontend/nginx.conf` is twelve lines and sets no `Content-Security-Policy`,
`Strict-Transport-Security`, `X-Frame-Options`, `X-Content-Type-Options` or
`Referrer-Policy`. The token lives in `localStorage` (`AuthContext.jsx:41-43`), read by
`utils/apiClient.jsx:8` and `features/chat/api/streamChat.js:23`.

Mitigating, and worth recording so it is not re-audited: there is **no XSS sink today** —
no `dangerouslySetInnerHTML`, no `innerHTML`, no `eval()` anywhere in `src/`. The finding is
the absence of defence in depth, not an exploitable path. Moving to an HttpOnly cookie is
blocked by SEC-3.

CSRF is genuinely a non-issue here: auth is an `Authorization` header, not a cookie. CORS is
an explicit origin list in all 12 services, never a wildcard — that part is fine. The
`allow_credentials=True` sprinkled around is unnecessary but not exploitable.

Also minor: the JWT carries `username` and `email` as claims (`user-service/app/auth.py:28-34`),
so PII sits in `localStorage` in cleartext. `sub`/`user_id` would do — `/users/me` already exists.

### SEC-7 — CSV upload: no size limit, no MIME check, whole file in memory · MEDIUM

**Closed by [P2-29](../plans/2026-07-28-p229-csv-upload-guards.md) on 2026-07-28.** Three of the
references below were stale when the plan was written and are corrected in place; the
severity claim was **confirmed by measurement**, see the plan's Outcome.

`transaction-service/app/adapters/inbound/rest_api.py:141` (was cited as `:107-116`) does
`content = await file.read()` with no `content_type` validation, no size guard and no streaming;
the parsers then load it again into `io.StringIO`
(`app/application/csv_parsers/nordea.py:34`, `danske_bank.py:35`, `internal.py:34` — the sweep
placed these under `adapters/inbound/`, they live under `app/application/`). There is no
ASGI-level max request size and no row-count cap. P3-15 chunked the *internal saga* path only —
the CSV path is untouched.

"Doubled footprint" **understated it: there are three live copies at peak**
(`bytes` → `str` → `StringIO`), against the pod's `limits.memory: 512Mi`
(`k8s/apps/transaction-service.yaml:42`).

Authenticated-only, so it is an availability issue rather than a breach: one user can OOM
transaction-service for everyone. **Measured, not presumed:** with the guard disabled via env on
a 512 MiB container, a 150 MB upload gives `OOMKilled=true, ExitCode=137`.

### SEC-8 — banking-service pins known-vulnerable versions · MEDIUM

`services/banking-service/requirements.txt:10` pins `python-jose[cryptography]==3.3.0`
(algorithm confusion CVE-2024-33663, JWE DoS CVE-2024-33664 — both fixed in 3.4.0); the
uv-managed services resolve to 3.5.0. `:1` pins `fastapi==0.115.0`, pulling starlette
0.38.x (multipart DoS CVE-2024-47874), against 0.135.1/0.52.1 elsewhere.

*The pins are verified; the CVE mapping is from memory — confirm with `pip-audit` before
acting.* This is the concrete consequence of P3-23 (banking has no `pyproject.toml`), which
currently reads as a tooling inconsistency rather than a vulnerability.

### SEC-9 — No dependency scanning in CI · MEDIUM

`.github/workflows/` contains only `ci.yml`. No dependabot, no `pip-audit`, no `npm audit`,
no CodeQL. Bandit runs (`ci.yml:122-128`) but is SAST, not SCA — it cannot see vulnerable
dependencies. Meanwhile `docs/security-audit-notes.md` defers nine npm advisories to "after
Phase 2", and `package-lock.json:5562-5587` still has `react-router-dom` at 7.6.3 where that
note's own fix range is `> 7.11.0`. Phase 2 has been code-complete since 2026-07-16, so the
deferral's condition has expired.

### SEC-10 — Four containers run as root · MEDIUM

No `USER` directive in `services/{account-service,gateway-service,frontend,serverless-health-job}/Dockerfile`;
the other ten have `USER appuser`. Gateway is the most exposed of the four. Separately, the
~50 k8s Deployments have no `securityContext`/`runAsNonRoot`/`readOnlyRootFilesystem` and
there is no NetworkPolicy anywhere, in a namespace where everything can reach everything.
P3-01 mentions non-root Docker as one clause of a large account-service refactor; the other
three are uncovered.

Also: Grafana ships `admin/admin` (`k8s/monitoring/grafana.yaml:20-23`,
`docker-compose.monitoring.yml:41-42`), and Grafana can read Loki, which promtail fills with
logs from every pod. Not in `k8s/secrets.yaml`, not covered by P2-15.

### SEC-11 — Upstream error bodies leak to the client · LOW

`banking-service/app/adapters/outbound/enable_banking_client.py:110-114` puts 200 characters
of Enable Banking's raw response into the exception message, and
`app/adapters/inbound/bank_api.py:118` returns it as the `detail` of an HTTP 502. What EB
puts in error bodies is unknown — *suspected*, not verified, that it can include session or
account identifiers. The callback path in the same file already does this correctly
(opaque `code=`/`ref=` correlation id, `bank_api.py:128-199`); `/connect` and `/sync` do not.

### Verified clean — do not re-audit these

- **Logging**: four hits total for logger-plus-credential patterns across all services and
  `scripts/`, all harmless. No PII, no tokens. None of the 33 frontend `console.*` calls
  touch the token or user data.
- **SQL injection**: none. All repositories use SQLAlchemy parameters. The two `text(f"...")`
  in `categorization-service/app/workers/transaction_consumer.py:220,236` interpolate an
  `int` module constant — not injectable, but not a pattern to copy.
  `scripts/cleanup_pg_duplicates.py:106,117,152` uses `%s` correctly. ES painless scripts are
  parameterised (`transaction_store.py:137,167`). No path traversal anywhere.
- **Ownership checks**: goal-service (`service.py:23-27`, called from all 8 mutations),
  transaction-service (`find_by_id(id, user_id)` on get/update/delete), notification-service
  (all 5 routes scope by `user_id`), analytics (`user_id` from token, `account_id` filter
  only), saga status (double-checked in `main.py:52-54` + gateway `saga_api.py:44-49`).
  OAuth state is single-use, expiring and bound to `user_id`
  (`postgres_pending_auth_repository.py:41-57`); the callback redirect is a fixed
  `FRONTEND_URL` — no open redirect.
- **Tracked secrets**: `git ls-files | grep -E 'pem|\.env'` returns only example files plus
  `k8s/secrets.yaml` and `k8s/keda/keda-rabbitmq-secret.yaml` (SEC-1). `.gitignore:5,11`
  correctly covers `**/.env` and `*.pem`; the two root PEMs are untracked and mounted `:ro`.
  P1-08 holds. The outstanding item there remains the already-documented history-rewrite
  decision.

---

## 2 — Frontend UX (`UX-*`)

The frontend is stronger than its reputation in the notes: design tokens are complete and
good (`src/index.css:11-112`), Radix-based Modal/ConfirmDialog have real focus management
including a deliberate DOM order so Enter cancels (`ConfirmDialog.jsx:59-64`), toasts have
correct paired polite/assertive live regions (`NotificationContext.jsx:65-105`),
`prefers-reduced-motion` is respected, empty states are broad and action-oriented, and the
transactions table has a proper mobile card view via `data-label`
(`TransactionsList.css:184-223`). No `alert()` anywhere. Confirmation dialog copy is
genuinely well written — `BudgetPage.jsx:156-163` warns about bank-sync lag before an
irreversible money movement.

The gaps below are real but should be read against that baseline.

### UX-1 — No user menu, no settings surface

`components/Navigation.jsx:42-44`: logout is a bare text button in the navbar next to
"Logget ind som: X". There is no avatar, no dropdown, no profile page, no settings page —
`grep` for settings/profil finds only the lucide `Settings` icon used as a tab label on the
goals page (`GoalPage.jsx:39`). This is the UI half of §0; the backend half is F2-08.

Adjacent: **there is no account switcher in the navbar at all**, and
`pages/AccountSelector.jsx` renders without `<Navigation>` (`App.jsx:59-62`) — no logout, no
way back. Users reach it by knowing the URL or by falling through an empty state
(`CategoriesPage.jsx:83`, `BudgetPage.jsx:232`).

### UX-2 — Hard reload on 401, no 404 route

`utils/handleUnauthorized.js:6-14` does `window.location.replace('/login')` — a full page
reload with no "your session expired" message and no returnUrl, so the user silently loses
their context. With 60-minute tokens and no refresh (§0) this fires regularly.
`apiClient.jsx:55` deliberately returns a never-resolving promise to stop the caller.

There is no `path="*"` inside `AppContent` (`App.jsx:31-40`), so `/foobar` renders the navbar
above a blank page. And there is no account gate: Dashboard and Transactions do not handle a
missing `account_id`, though BudgetPage and CategoriesPage do.

### UX-3 — Mobile navigation is effectively hidden

`styles/Navigation.css:130-141` makes the seven nav links a horizontally scrolling strip with
`scrollbar-width: none` and `::-webkit-scrollbar { display: none }`. On a phone there is no
visual affordance that more links exist, so "Mål" and "Finans Chat" are unreachable in
practice. No hamburger anywhere in the codebase, no bottom nav, and touch targets are
`padding: 0.35rem 0.625rem` at the 480px breakpoint (`Navigation.css:168-171`) — far under
44px. Meanwhile "Logget ind som: X" plus the logout button keep their space and never
collapse (`Navigation.css:144-151`).

### UX-4 — Loading and error presentation is inconsistent

No skeletons anywhere (zero hits for skeleton/shimmer); two ad-hoc spinners. Loading text
uses **four different verbs across eight strings** — "Loader...", "Loader…", "Indlæser
dashboard...", "Indlæser transaktioner...", "Indlæser regler…", "Henter budget...", "Henter
mål...", "Henter historik…" — with mixed `...` and `…`. Page transitions blank the whole
layout rather than preserving it (`DashboardOverview.jsx:67` returns early), producing a
large layout shift. No `aria-live`/`aria-busy` on loading states, so none of it is announced.

Errors go three ways: toasts (`NotificationContext.jsx:38-39`), inline `.error-message`
(`LoginPage.jsx:51`, `RegisterPage.jsx:76`, `AccountSelector.jsx:97`), and `MessageDisplay`
with hardcoded inline hex that bypasses the token system entirely (`MessageDisplay.jsx:6-16`,
e.g. `'#fef2f2'` where `var(--color-error-50)` exists). `GoalSetup.jsx:59,101-103` shows the
same error twice at once — locally *and* as a toast.

Error toasts correctly do not auto-dismiss while success ones do
(`NotificationContext.jsx:32-34`) — that part is deliberate and right.

### UX-5 — CLAUDE.md's form convention does not exist in the code

The conventions specify React Hook Form + Zod with trim-then-validate. **Neither package is
installed** (`package.json`). All seven forms are hand-rolled `useState` with an imperative
if-chain producing a single global error string: Login (`LoginPage.jsx:53-85`, HTML `required`
only), Register (`:23-34`), Transaction (`TransactionForm.jsx:56-112`), Rule
(`RulesPage.jsx:69-94`), Goal (`GoalSetup.jsx:69-104`), Category
(`CategoryManagement.jsx:155-183`), Budget lines (`BudgetPage.jsx:184-208`, no validation at all).

Consequences: no field-level errors, no `aria-invalid`, no `aria-describedby`, no blur
validation, no focus move to the failing field. `TransactionForm.jsx:61` says "Alle felter
skal udfyldes." when four fields are empty and points at none of them. The amount field is a
raw `type="number"` with no `step`/`min` (`:128-134`) although the backend requires ≥ 0,01 —
and a comment at `:65-66` acknowledges exactly that. `TransactionForm.jsx:60-63` and `:71-74`
validate `category` twice (dead code). No dirty-tracking, so a half-filled modal form is
discarded by Esc without warning.

Either the convention or the code should move. Worth noting `patterns/frontend-data-patterns.md`
already flags which CLAUDE.md claims are aspirational — this one belongs on that list.

### UX-6 — Accessibility gaps

Against the good baseline above:

- `components/NotificationBell/NotificationBell.jsx:82-88` — each notification is a clickable
  `<div>` with no `role`, `tabIndex` or `onKeyDown`; it cannot be marked read from the
  keyboard. It sits inside `role="menu"` (`:61`) with no `menuitem` children, which is invalid
  ARIA. The dropdown closes on outside `mousedown` (`:34`) but not on Esc or Tab-out.
- **No `role="progressbar"`/`aria-valuenow` on any progress bar** — `GoalItem.jsx:97-105`,
  `GoalOverview.jsx:112-115`, `BudgetProgressSection.jsx:18,40,93`, `BudgetPage.jsx:430-432`,
  `GoalProgressSection.jsx:23`. These bars are the app's primary visualisation and convey
  nothing to a screen reader.
- Tabs without tab semantics: `GoalPage.jsx:51-63` — styled buttons, no `role="tablist"/"tab"`,
  no `aria-selected`, no arrow-key navigation.
- No skip link to `<main>`; keyboard users traverse 7 nav links + bell + logout on every page.
- `.visually-hidden` is defined only in `DashboardOverview.css:163` but used by
  `TransactionsPage.jsx:184` — works solely because all CSS is one global bundle.
- Deprecated `onKeyPress` at `AccountSelector.jsx:154`; raw emoji without `aria-hidden` at
  `BudgetPage.jsx:229`; wrapping labels without `htmlFor`/`id` in
  `CategoryManagement.jsx:157-176`.

### UX-7 — Onboarding and CSV feedback

There is no onboarding: register → login → account selector → dashboard, with nothing
explaining how account/category/budget/goal/rule relate. A new user **cannot create a
transaction until she has manually created a category** — `TransactionForm.jsx:143` disables
the category select when the list is empty without saying why. The empty-database dashboard
shows one `no-data` block (`DashboardOverview.jsx:69-78`) while the bank widget, budget and
goals sections sit below it as empty boxes.

CSV import throws away `result.errors` from the API (`TransactionsPage.jsx:141-158` vs
`api/transactions.jsx:59`), so the user never learns *which* rows were skipped. No dry-run or
preview, no drag-and-drop, and the chosen filename is not displayed
(`TransactionsPage.jsx:233-238`). The upload section is also placed *above* both the
"Tilføj ny transaktion" button and the list itself (`:219-259`) — the rarest action in the
most prominent slot. The file input is reset via
`document.querySelector(...)` (`:155`), i.e. DOM manipulation around React.

### UX-8 — Smaller items, grouped

- No dark mode: zero hits for `prefers-color-scheme` or `data-theme` in `src/`. With the
  existing tokens this is close to free. `<meta name="theme-color" content="#000000">`
  (`index.html:7`) currently matches nothing.
- Global CSS with no scoping — `.form-group`, `.button`, `.progress-bar`, `.error-message`
  are global names reused across files. `Modal.jsx:23-25` prefixes `app-modal-*` specifically
  to dodge collisions, which acknowledges the problem without solving it.
- Tokens are bypassed with hardcoded hex in `GoalItem.jsx:6-11,29-35` (a different palette
  entirely), `MessageDisplay.jsx:11-13`, `CategoryManagement.jsx:180`, `Navigation.css:54,84,91,97`.
- No refresh affordance anywhere, although `lib/queryClient.js:36` sets
  `refetchOnWindowFocus: false` with a comment that users "can refresh explicitly" — they cannot.
  The only manual refresh is per-bank-connection "Sync nu".
- Currency formatting is done three ways: manual `toFixed(2) + " DKK"`
  (`TransactionsList.jsx:92`), `formatAmount` (`lib/formatters.jsx`), and `formatKr` (BudgetPage).
- No per-route `<title>`; the tab always says "Finans Tracker".
- The transactions default period is the calendar month (`TransactionsPage.jsx:36-43`) while
  the dashboard respects the account's `budget_start_day` (`DashboardOverview.jsx:109-113`) —
  a concrete instance of the confusion F2-07 is about.
- Inline re-categorisation closes the select on `onBlur` (`TransactionsList.jsx:96-116`), which
  in some browsers cancels the choice before `onChange` fires.
- ErrorBoundary wraps only `<Routes>` (`App.jsx:30`) — not Navigation, login, register or the
  account selector.

---

## 3 — Performance & ops (`OPS-*`)

Runtime performance is **fine and does not need work**: 359 ES documents, empty DLQs, no
queue backlog, CI jobs under 72 s, transaction-service's 220 tests in 14 s. Aggregations are
correct — `analytics-service/.../query_store.py` uses `size=0` on every aggregation query
(`:253,304,347,429,651`) with no client-side summing anywhere, and no `limit=10000` patterns
exist outside `backfill_embeddings.py`, which correctly uses `search_after`.

The costs are in the build and distribution layer instead. All figures below were measured
against the running stack on 2026-07-26.

### OPS-1 — Build and image hygiene · the highest effort-to-payoff item here

- **gzip is off**: `services/frontend/nginx.conf` sets no `gzip`, and the base image has it
  commented out. Measured in the image: `index-*.js` 774 751 B + `index-*.css` 99 056 B =
  874 KB uncompressed on every cold load, ~250 KB with gzip. No `Cache-Control: immutable`
  on the hash-named assets either, so a refresh revalidates everything.
- **No `.dockerignore` anywhere**, and `context: .` on 50+ compose services. Measured: repo
  1,7 GB, of which `services/*/.venv` is 1,1 GB, `services/frontend/node_modules` 228 MB,
  `.git` 108 MB. Worse, the three shared packages' **dev `.venv` are baked into every image** —
  `docker history` shows `COPY services/shared/auth` = 42,3 MB, `messaging` = 32,8 MB,
  `contracts` = 19,3 MB, against source sizes of 36K/196K/212K. That is ~92 MB of ballast
  × 12 Python services.
- **uv cache left in the image**: every Dockerfile runs `uv sync --frozen --no-dev` without
  `--no-cache` (e.g. `transaction-service/Dockerfile:16`), leaving `/root/.cache` at 98 MB.
  Current images run 460 MB (analytics) to 782 MB (notification-consumer);
  `docker system df` reports 57 GB.
- **The frontend Dockerfile copies the host's `node_modules` over its own install**:
  `services/frontend/Dockerfile:8-11` runs `npm install` and then `COPY services/frontend/ ./`.
  Without a `.dockerignore` that overwrites the freshly built linux binaries with the
  developer's darwin-arm64 ones — 228 MB of wasted I/O per build and a latent
  `Cannot find module @esbuild/linux-arm64`.

One `.dockerignore` (`**/.venv`, `**/node_modules`, `**/__pycache__`, `**/.pytest_cache`,
`.git`), `ENV UV_NO_CACHE=1`, and two lines of nginx config remove roughly 190 MB of ~660 MB
per image and fix the frontend build hazard. Multi-stage is then not worth it — 13 of 14
Dockerfiles are single-stage and there is little left to win.

### OPS-2 — Compose drift left over from P2-16

- **No `restart:` policy on any datastore**: redis (`:36`), postgres (`:48`), rabbitmq (`:65`),
  elasticsearch (`:79`), ollama (`:99`) and all eight service Postgres instances
  (`:152,260,323,448,569,686,905,1015`). P2-16 added restart policies to APIs and outbox
  publishers but not to the databases underneath them, so after a Docker daemon restart every
  app comes back `unless-stopped` while its database stays down — crash-loop until someone
  runs `compose up` by hand. Exactly the failure class P2-16 set out to close.
- **Elasticsearch is at 771 MiB of its 1 GiB `mem_limit`** (`docker-compose.yml:86-87`,
  `-Xmx512m` heap plus off-heap) at 359 documents. It is the only container with a limit and
  the one closest to an OOM kill. Either raise `mem_limit` to 2g or lower `-Xmx`.
- **No resource limits on the other 55 containers** — ~2,5 GB total measured across 56
  containers. P3-11 covers this for k8s; the compose side is uncovered.
- **26 worker containers have no healthcheck** and none of the 14 Dockerfiles declare
  `HEALTHCHECK`, so a dead consumer shows as "Up" in `docker ps`. Again P3-11 is worded for
  k8s only.
- **Orphaned `transactions_v1`** — 222 documents, 106 kb, no alias pointing at it
  (`transactions` → `transactions_v2`). Dead data in the memory-pressed cluster; same class of
  drift as P3-21.

### OPS-3 — Frontend bundle: no code splitting

`src/App.jsx:16-23` imports all eight pages eagerly; the only `React.lazy` in the codebase is
for devtools (`:72`). `vite.config.js:9-11` has just `outDir` — no `manualChunks`, no
`chunkSizeWarningLimit`, no visualizer, no bundle budget in CI. Result is the single 757 KB
chunk measured in OPS-1, which puts `recharts` (dashboard only), `graphql`+`graphql-request`
(gateway hooks only) and `@microsoft/fetch-event-source` (chat only) on the login page's
critical path.

### OPS-4 — Gateway opens a new connection pool per upstream call

Six sites construct `with httpx.Client(...)` inside the method:
`adapters/outbound/analytics_client.py:46`, `account_client.py:26`, `budget_client.py:33`,
`category_client.py:34,43`, `saga_client.py:26`. The dashboard's single GraphQL query
(`hooks/useDashboardData/useDashboardData.jsx:17-91`) fans out to ~7 sequential upstream calls
— `_overview_with_trend` (`graphql_api.py:284-297`) alone makes two analytics calls in a row —
each with its own TCP handshake and no keep-alive reuse.

**This is not P2-04.** P2-04 is the *async* rewrite, deliberately rolled back and parked until
measured need. Connection pooling is orthogonal: one module-level or lifespan-scoped
`httpx.Client` per upstream, ~20 lines, no async required. Per-request memoisation already
exists as a house pattern (`graphql_api.py:231,242-249`).

The secondary issue *is* P2-04's territory: the resolvers are sync (`def period_overview`, …)
under an async `GraphQLRouter` (`main.py:38`), so blocking httpx calls run on the event loop
and one slow analytics query serialises all concurrent users. Not observable at one user.

### OPS-5 — Notification bell polls two queries where one would do · LOW

`hooks/useNotificationFeed.jsx:30,37` sets `refetchInterval: 45_000` on both the list and the
count query, and the hook lives in `Navigation`, so it runs on every authenticated page
whether or not the dropdown is open. Not a busy loop — TanStack v5 pauses polling on blur and
`refetchIntervalInBackground` is unset — but the list already returns 50 rows *including*
`is_read`, so the unread count can be derived client-side and the traffic halved. The backend
side is correct: `notification-service/app/models.py:40` has
`ix_notifications_user_created (user_id, created_at)` covering both queries.

Saga polling (`api/saga.jsx:49-71`, 1500 ms, 300 s timeout → up to 200 calls) is bounded and
only runs during an active sync. Fine.

### OPS-6 — Idle outbox polling and a missing composite index · LOW, note-only

Eight outbox workers at `POLL_INTERVAL_S = 2.0` (`shared/messaging/messaging/worker.py:45`,
and it only sleeps when a batch came back empty — `:130-137` — which is the right
construction) means ~4 `SELECT … FOR UPDATE SKIP LOCKED` per second against eight separate
Postgres instances, around the clock: ~350k queries a day to discover nothing.
LISTEN/NOTIFY would remove it. Costs nothing at this scale; the kind of thing that surprises
you on a cloud database bill.

Separately, `transaction-service/app/models.py:53-61` has single-column indexes but nothing
matching the list query's actual shape — filter on `user_id`+`account_id`+date range, sort by
`(date DESC, id DESC)` (`postgres_transaction_repository.py:91`). At 359 rows it is irrelevant.
Recorded as "do this if an account passes ~50k rows": `(account_id, date DESC, id DESC)`.
No other missing indexes were found across the ten model files reviewed.

### OPS-7 — CI: no dependency cache, and `uv sync` runs without `--frozen`

`.github/workflows/ci.yml:82-84` uses `actions/setup-python@v5` with no `cache:`, and `:89`
reinstalls uv+pytest+ruff+bandit from scratch on each of the 12 Python jobs — an estimated
10–20 s per job. The frontend job caches correctly (`:220-221`).

More important than the cache: `:93` runs `uv sync --dev` **without `--frozen`**, so the
lockfile is never validated in CI. That is a correctness hole, not a performance one — a
drifted lockfile passes silently. Fix it when someone touches that line.

Test-suite speed needs no work. Ten `scope="module"` PostgresContainer fixtures are declared
in test files rather than a session-scoped conftest (5 of them in transaction-service alone),
but a warm container start measured ~3 s, so consolidating would save ~12 s there and ~30 s
across the repo. Not worth it. No `pytest-xdist` needed — the CI matrix already parallelises
per service.

---

## 4 — Two backlog rows that overstate what shipped

Both are the same pattern, and it is the one recorded in the exam note about event delivery:
*"implemented"* and *"switched on in production"* are different claims.

- **P2-19** is marked done with the text "prefetch >1 where idempotent". No consumer in the
  repo has prefetch > 1: `shared/messaging/messaging/consumer.py:55` defaults to
  `DEFAULT_PREFETCH_COUNT = 1`, and all five explicit `set_qos` calls pass 1
  (`analytics/projection_consumer.py:77`, `analytics/embedding_consumer.py:72`,
  `transaction/saga_command_consumer.py:50`, `banking/saga_command_consumer.py:139`).
  The practical effect is that the ES projection handles one event at a time with a full ack
  round-trip between each — the ceiling on the whole ADR-0003 chain during a 500-row bulk
  import. Harmless today; the problem is that the row makes it look like the ceiling was raised.
- **P2-02** is marked done with `require_exp` in its title. See SEC-2 — built, never enabled.

Corrected in place in BACKLOG.md with dated notes rather than by editing the original claims.

---

## Backlog mapping

| Finding | Backlog |
|---|---|
| tx list truncation (own doc) | **P1-14** |
| SEC-1 secret disclosed | **P1-15** (with the categorize doc) / rotation step |
| `/categorize` unauth (own doc) | **P1-15** |
| SEC-2 `require_exp` | **P2-26** |
| SEC-4 rate limiting | **P2-27** |
| SEC-5 taxonomy authorisation | **P2-28** |
| SEC-7 CSV upload guards | **P2-29** |
| SEC-3 perimeter decision | **P3-24** (decision first) |
| SEC-6 security headers | **P3-25** |
| SEC-8/9 SCA + banking pins | **P3-26** |
| SEC-10 non-root + k8s securityContext | **P3-27** |
| OPS-1 build/image hygiene | **P3-28** |
| OPS-2 compose drift | **P3-29** |
| OPS-3 code splitting | **P3-30** |
| OPS-4 gateway pooling | **P3-31** |
| UX-2/3 routing + mobile nav | **P3-32** |
| UX-4/5/8 UI consistency | **P3-33** |
| UX-6 a11y | **P3-34** |
| §0 user domain | **F2-08 / F2-09 / F2-10** |
| UX-7 onboarding + CSV feedback | **F2-11 / F2-12** |
| UX-8 dark mode | **F2-13** |
| §4 backlog accuracy | corrected in place |
