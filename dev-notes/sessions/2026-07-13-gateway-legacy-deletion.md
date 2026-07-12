---
date: 2026-07-13
topic: Working-tree lukket (EB active-app + e2e-format) og gatewayens legacy analytics-read-sti slettet (ADR-0004 §Oprydning udført)
---

# Session 2026-07-13 — commit-hygiejne + gateway legacy-sti-sletning

Punkt 0+1 fra prioriteringsoverblikket (se plan 2026-07-12-ai-service-es-chat for
det videre AI-spor).

## Done

- **Working tree lukket** (2 commits): EB compose-vars omlagt fra `SANDBOX_`- til
  `ENABLE_BANKING_ACTIVE_*`-prefix (kan nu pege på sandbox ELLER produktions-app;
  produktions-apps kræver https-redirect — dokumenteret i example.env), og
  `tests/e2e/` ruff-formateret mod root-config. `dev-notes/Welcome.md`
  (Obsidian-boilerplate) slettet.
- **Gateway legacy analytics-read-sti slettet** (ADR-0004 §Oprydning, muliggjort af
  AI-19 i går): REST `/dashboard/*` (`rest_api.py`), `AnalyticsService`-aggregeringen
  (`application/service.py`), `HttpAnalyticsReadRepository` (`transaction_client.py`),
  `LegacyFinancialAnalyticsAdapter`, `DualReadFinancialAnalyticsRepository`,
  `IAnalyticsReadRepository`-porten, `_MemoizedAnalyticsReadRepository` +
  `build_financial_analytics_port` i graphql_api, `ANALYTICS_READ_SOURCE`-flaget
  (config/compose/k8s-configmap) og 5 testfiler. GraphQL-konteksten bygger nu altid
  én `HttpFinancialAnalyticsRepository` (implementerer begge read-porte).
- Gatewayen kalder ikke længere transaction-service: `TRANSACTION_SERVICE_URL` ude
  af gateway-config + compose; `depends_on` transaction-service → analytics-service.
- ADR-0004 §Oprydning markeret UDFØRT; arkitekturnoten
  `architecture/services/gateway-service.md` genskrevet til as-built.

## Verified

- Gateway: 23 tests grønne (nyt `.venv` oprettet — gateway manglede et, søsterne
  havde), ruff ren, `docker compose config -q` ok.
- **Live smoke i compose** (rebuildt image): `/health` ok, `/api/v1/dashboard/overview/`
  → 404 som forventet, GraphQL `currentMonthOverview` → reelle ES-backed tal inkl.
  trend (dev-JWT, X-Account-ID: 1).

## Learned / gotchas

- Audit-fundklasserne "unbounded full-history fetch on every read" (CRITICAL) og
  "no per-request memoization" (HIGH) i gatewayen er **bortfaldet** med sletningen —
  de sad alle i legacy-stien. P2-04's async-motivation er tilsvarende svækket;
  genovervej kun ved målt latency-problem.
- Flag-rollback (`ANALYTICS_READ_SOURCE=legacy`) findes ikke længere — rollback er
  nu `git revert` af sletnings-commiten.
- `account-service-consumer` restarter i loop i den kørende stack (eksisterende
  tilstand, urelateret til denne session) — værd at kigge på ved næste stack-arbejde.
- Git-identitet var ukonfigureret på denne maskine → repo-lokal `user.name`/`user.email`
  sat til at matche historikken (jothom2912).

## Open ends / next (per prioriteringsoverblik 2026-07-13)

1. **AI-20** (ES hybrid search erstatter ChromaDB) — FØRST: hærd eval-settet
   (distractors; baseline er mættet 1.000) + skriv embed-worker-placerings-decision.
2. AI-02/AI-21 (slots + taxonomy resolve), så F1-02/F1-03 (unblocked af P2-06).
3. P2 verification-sweep + shared-package adoption løbende.
4. Undersøg `account-service-consumer` crash-loop.
