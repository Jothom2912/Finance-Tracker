---
title: frontend (React + Vite SPA)
updated: 2026-07-07
source: architecture audit 2026-07-07
---

# frontend (port 3000)

~9,000 lines untyped `.jsx`/`.js`. **No Redux** (despite older docs): TanStack Query v5 + React Context (`AuthContext`, `NotificationContext`, `ConfirmDialogProvider`) + a `useReducer` phase machine for chat.

## Structure

- **Routing**: react-router v7, two-level; guards duplicated inline in `App.jsx` (`PrivateRoute.jsx` exists but is unused).
- **API layer — 3 clients**: `utils/apiClient.jsx` (fetch wrapper: auth headers, timeout, 401 → global logout redirect via never-resolving Promise), `api/graphqlClient.jsx` (graphql-request → gateway reads), `features/chat/api/streamChat.js` (POST-SSE). `api/crudFactory.jsx` generates consistent CRUD modules.
- **Direct service coupling**: `config/serviceUrls.js` hardcodes 9 base URLs — the SPA calls 8 microservices directly; gateway used only for GraphQL reads + saga status.
- **Auth**: JWT + user/account identity in localStorage (17 files read it); no expiry decoding, no refresh; `isAuthenticated()` checks presence only.
- **Best slice**: `features/chat/` (streamChat → useChatStream → chatReducer) — clean, tested.
- **Dead weight**: 3,534-line unused hexagonal `components/Budget/` module (+ dead `api/budgets.jsx`, `CSVUpload/`, `PrivateRoute.jsx`); committed `build/` output.

## Data flows

- **Login**: user-service REST → AuthContext writes localStorage + state → account-selector picks `account_id` → all clients re-read localStorage per request (`Authorization` + `X-Account-ID`).
- **Dashboard**: one `useQuery` keyed `['dashboard', {accountId, month, year}]` → gateway GraphQL (`CURRENT_MONTH_QUERY` or `PERIOD_QUERY`) + separate REST goals query.
- **Transaction create**: form calls API module directly (not useMutation) → invalidates `['transactions']` + `['dashboard']` but NOT `['periodOverview']` → Categories page goes stale (and vice versa for category renames).

## Open problems

See [findings/2026-07-07-architecture-audit.md](../../findings/2026-07-07-architecture-audit.md). Headliners: tokens in localStorage without expiry handling (HIGH), 3.5k lines dead Budget module (HIGH), broken login 403 fallback dead-ends silently (HIGH), goals fetched 3 independent ways + `refreshTrigger` prop plumbing (HIGH), cache-invalidation gaps between pages (MEDIUM), currency formatting duplicated 6+ ways with visibly inconsistent output (MEDIUM), no transaction pagination/virtualization (MEDIUM), snake_case/camelCase dual shapes leaking into components (MEDIUM), non-reactive `account_id` from localStorage in query keys (MEDIUM).

## Strengths

Chat feature slice, crudFactory, parseApiError, query-key factories, NotificationContext aria-live, saga polling UX, 25+ colocated test files.
