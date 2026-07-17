---
title: "Pattern: frontend data layer"
updated: 2026-07-17
source: frontend doc 2026-07-07; F1-02/03 UI work 2026-07-17
---

# Frontend data layer

React/Vite SPA, **no Redux**: TanStack Query v5 for server state + small React Contexts
(`AuthContext`, `NotificationContext`, `ConfirmDialogProvider`) + `useReducer` only for
the chat phase machine. Detail:
[architecture/services/frontend.md](../architecture/services/frontend.md).

## The house patterns

- **`api/crudFactory.jsx`** generates consistent CRUD modules —
  `createCrudApi('/rules', {baseUrl: CATEGORIZATION_SERVICE_URL})` is the template
  (rules page, F1-02). New resource → factory call, not a hand-rolled module.
- **Three clients, pick by need**: `utils/apiClient.jsx` (fetch wrapper: auth headers,
  timeout, 401 → global logout), `api/graphqlClient.jsx` (gateway reads),
  `features/chat/api/streamChat.js` (POST-SSE).
- **Service URLs** only from `config/serviceUrls.js` — never inline base URLs.
- **Query-key factories + central invalidation**: mutations go through `useMutation` and
  invalidate via the shared `invalidateFinancialData` helper (P2-18) — manual
  invalidate-lists drift (the pre-F1 TransactionForm bug class).
- **Forms**: house pattern is controlled `useState` forms — CLAUDE.md's RHF/Zod section
  is **aspirational**, nothing uses it yet (code survey 2026-07-17). Follow the house
  pattern; copy `CategoryManagement.jsx` for CRUD admin pages.
- **Never crash on missing denormalized data** — fall back to ID lookup
  ([read-copies-and-denormalization](read-copies-and-denormalization.md)).
- **Best slice to imitate**: `features/chat/` (streamChat → useChatStream → chatReducer),
  clean and tested.

## Gotchas (open findings)

- JWT + identity in localStorage, no expiry decoding/refresh; `account_id` read from
  localStorage is non-reactive in query keys (MEDIUM).
- Cache-invalidation gaps between pages persist where mutations bypass `useMutation`.
- 3.5k-line dead `components/Budget/` module — don't extend it; it's deletion-listed.
- Currency formatting exists 6+ ways — reuse, don't add a 7th.
