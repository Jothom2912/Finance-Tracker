---
date: 2026-07-12
topic: Executed plan 2026-07-11-es-analytics-integration — steps A (commit+rebase) and B (ES bring-up, backfill, dual-read re-verify)
---

# Session 2026-07-12 — ES analytics integration (steps A + B)

Executed [plans/2026-07-11-es-analytics-integration.md](../plans/2026-07-11-es-analytics-integration.md).
Safety tag `pre-es-rebase` marks the pre-integration HEAD.

## Step A — commit + rebase (done)

- Working tree (P1 remainder + interrupted Phase 2) committed in 6 logical commits, then
  `phase-1-fixes` rebased onto `origin/master` (14 ES-analytics commits). History is linear.
- **Async decision executed**: P2-04's half-done async conversion rolled back to sync
  (pure-async files reverted; `transaction_client`/`saga_client` hand-restored to sync
  keeping pagination/auth-forwarding; unwired `http_client.py` deleted). The new gateway
  tests document the sync contract.
- Conflicts resolved as planned: `graphql_api.py` (master's `build_financial_analytics_port`
  kept; local `_MemoizedAnalyticsReadRepository` injected into the legacy branch via a new
  `transactions_cache` param) and `useDashboardData.jsx` (master's `DASHBOARD_QUERY` +
  local `useGoals()`; two orphaned helpers deleted).
- **Gotcha fixed**: `shared/contracts/tests` (regular package) shadows gateway's `tests`
  namespace under the Makefile's PYTHONPATH → master's `test_legacy_analytics_adapter.py`
  could not import. Fixed with `services/gateway-service/tests/__init__.py`. (Likely broken
  on master's CI too, if it uses the Makefile paths.)
- Verified: gateway 52/52, frontend 218/218, compileall clean, compose config valid.
- Note for Windows devs: service Makefiles use `:` as PYTHONPATH separator — run pytest
  with `PYTHONPATH="../shared/contracts;../shared;."` locally.

## Step B — ES stack bring-up + verification (done)

- **Found & fixed: categorization-transaction-consumer crash-loop** — P2-06 was left
  half-migrated (`main()` built the old engine with unimported `SEED_MERCHANT_MAPPINGS`;
  `_categorize` used removed attributes). Finished the provider wiring per the module's
  own docstring; 51 unit tests green; verified live (RuleEngine: 130 keywords, 41 subcats
  from DB). P2-06 → done.
- **Stale ES indices from an older iteration** (`transactions`, `accounts`, `goals`, plus
  extras like `users`/`budgets` the new service never creates) blocked bootstrap
  (`invalid_alias_name_exception`). Deleted the three colliding ones (projections are
  rebuildable per ADR-0004); bootstrap then created all four `*_v1`-behind-alias indices.
  Leftover stale indices still present (harmless): `categories`, `users`, `budgets`,
  `planned_transactions`, `account_groups` — delete when convenient.
- P1 deploy action #1 already satisfied: `account_service.account_creation` has DLQ args,
  consumer connected.
- **Backfill** run for users 1–4: transactions 419 (= source DB), accounts 7, taxonomy 51,
  goals 0 (= source DB; old ES goals data was stale).
- **Dual-read re-verification under the merged code**: made `ANALYTICS_READ_SOURCE`
  env-overridable in compose (`${ANALYTICS_READ_SOURCE:-analytics}`), ran gateway in
  `dual`, exercised periodOverview (3 data months), financialOverview, transactions,
  topSpendingCategories, currentMonthOverview → **14 shadow reads, 0 divergences,
  0 shadow errors**. Flipped back to `analytics`; ES numbers match dual-mode exactly;
  `searchTransactions` (danish stemming, "netto" → 39 hits) and cashflow OK.
- Legacy REST `/api/v1/dashboard/overview/` (ai-service dependency) verified working.
  Gotcha: with no date params it defaults to a rolling 30-day window — an empty result
  on old test data is correct behavior, not a bug.
- **P1 deploy action #2 (AI re-ingest) done** — after fixing the P2-16 Ollama drift:
  ai-service pointed at `host.docker.internal:11434` while `ollama-pull` fills the compose
  container (qwen3:4b + bge-m3). Repointed to `http://ollama:11434`; re-ingest of user 1 →
  262 transactions into `transactions__bge-m3` (103s).

## Learned / surprised

- The "P1 opdateringer" framing hid that the working tree was actually P1-remainder + the
  interrupted Phase 2 — the phase2-in-flight session note was essential context.
- Master's dual-read wrapper only logs on divergence/shadow-error; confirm shadow traffic
  via analytics-service access logs, not gateway logs.
- Synthetic dev JWTs need `exp` (+`sub`) — categorization-service 401s without them;
  gateway accepts bare `{"user_id": N}`. The graceful-degradation path masked this.

## Open ends

- Plan steps C11–C12: analytics-service suite + remaining per-service P2 suites not run.
- Chat responder model `qwen3:8b` (config default) exists in neither host nor container
  Ollama — chat responder path untested; `ollama-pull` only fetches qwen3:4b + bge-m3.
- Users 2–4 not re-ingested (no/little data; ingest is per-user, X-Account-ID-scoped).
- Old stale ES indices left in place (see above).
- Wave-B adoption of shared packages + MIGRATION.md still pending (unchanged).
