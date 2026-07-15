# dev-notes index

One line per document. Add yours when you add a file (see `dev-notes` skill).

## Meta
- [README.md](README.md) — how this knowledge base works: structure, conventions, statuses.

## Architecture (living documents)
- [architecture/overview.md](architecture/overview.md) — system map, core patterns, data flows, the 5 systemic problems. **Start here.**
- [architecture/infrastructure.md](architecture/infrastructure.md) — compose/k8s/CI/monitoring topology + measured cross-service duplication map.
- [architecture/services/user-service.md](architecture/services/user-service.md) — auth service + how services/shared is consumed; outbox reference implementation.
- [architecture/services/transaction-service.md](architecture/services/transaction-service.md) — tx CRUD, CSV/bulk import, saga participant, taxonomy read-copies, 4 workers.
- [architecture/services/account-budget-goal-services.md](architecture/services/account-budget-goal-services.md) — the three CRUD siblings + their duplication; money flows (month-close → surplus → goal).
- [architecture/services/banking-and-saga-services.md](architecture/services/banking-and-saga-services.md) — PSD2/Enable Banking + saga orchestration, bank_sync flow end-to-end.
- [architecture/services/categorization-and-ai-services.md](architecture/services/categorization-and-ai-services.md) — rule-tier pipeline, taxonomy ownership (ADR-003), SSE chat pipeline, ChromaDB.
- [architecture/services/gateway-service.md](architecture/services/gateway-service.md) — read BFF (REST + GraphQL), fan-out reality, stubs, monolith footprint.
- [architecture/services/frontend.md](architecture/services/frontend.md) — React SPA: TanStack Query (no Redux), 3 API clients, direct service coupling.

## Findings
- [findings/2026-07-07-architecture-audit.md](findings/2026-07-07-architecture-audit.md) — full codebase audit: 10 CRITICAL, 27 HIGH, ~45 MEDIUM, ~40 LOW, with file:line evidence.
- [findings/2026-07-12-goal-migration-004-sqlite.md](findings/2026-07-12-goal-migration-004-sqlite.md) — goal migration 004 is Postgres-only; sqlite migration tests red (LOW, open).

## Backlog & plans
- [backlog/BACKLOG.md](backlog/BACKLOG.md) — technical backlog (P1 security/money → P2 systemic → P3 consistency), linked to finding IDs. P1 done 2026-07-07.
- [backlog/FEATURES.md](backlog/FEATURES.md) — feature backlog (F1 finish-half-built → F2 high-value → F3 bets), each with existing-scaffolding leverage + prerequisites.
- [backlog/AI-IMPROVEMENTS.md](backlog/AI-IMPROVEMENTS.md) — AI-service ideas: RAG ladder (hybrid search, reranking, multi-hop), router/responder upgrades, eval-first sequencing.
- [backlog/ML-CATEGORIZATION.md](backlog/ML-CATEGORIZATION.md) — ML categorization: getting-started ladder (merchant memory → baseline → shadow mode), feedback flywheel, hierarchical/zero-shot subcategory smarts.
- [plans/2026-07-07-refactoring-roadmap.md](plans/2026-07-07-refactoring-roadmap.md) — 4-phase execution strategy for the technical backlog, with verification approach.
- [plans/2026-07-07-feature-roadmap.md](plans/2026-07-07-feature-roadmap.md) — feature sequencing interleaved with refactor phases + build sketches for the top items.
- [plans/2026-07-11-es-analytics-integration.md](plans/2026-07-11-es-analytics-integration.md) — rebase phase-1-fixes onto master's ES analytics read-side (ADR-0004), bring-up/backfill/dual-read re-verify, + AI-19..21 ES-for-chat proposals.
- [plans/2026-07-12-ai-service-es-chat.md](plans/2026-07-12-ai-service-es-chat.md) — ai-service onto the ES read-store: AI-01 eval gate → AI-19 structured intents → AI-20 hybrid search replaces ChromaDB → AI-21 slots, + cleanup + chat-UI steps.

## Decisions
- [decisions/2026-07-13-embed-worker-placement.md](decisions/2026-07-13-embed-worker-placement.md) — AI-20 embedding writer: separate consumer in analytics-service on own queue `analytics.embeddings`, partial-update of `description_vector`.

## Sessions
- [sessions/2026-07-07-architecture-audit.md](sessions/2026-07-07-architecture-audit.md) — audit session: what was done, method, open ends.
- [sessions/2026-07-07-phase1-p1-fixes.md](sessions/2026-07-07-phase1-p1-fixes.md) — Phase 1: all 12 P1 critical fixes shipped, deploy actions, decisions needed.
- [sessions/2026-07-12-es-integration-rebase.md](sessions/2026-07-12-es-integration-rebase.md) — rebase onto master's ES read-side + stack bring-up: dual-read 0 divergences, backfill, P2-06 crash-loop fixed, Ollama drift fixed.
- [sessions/2026-07-12-ai-es-chat-wave1.md](sessions/2026-07-12-ai-es-chat-wave1.md) — wave 1 of ai-es-chat plan: AI-01 eval harness (baseline 1.000, saturated), AI-19 live-smoked, ports made real, junk deleted; legacy dashboard now deletable.
- [sessions/2026-07-13-gateway-legacy-deletion.md](sessions/2026-07-13-gateway-legacy-deletion.md) — EB active-app vars committed; gateway legacy analytics path + ANALYTICS_READ_SOURCE deleted (ADR-0004 cleanup done, live-smoked); audit's full-history-fetch finding class voided.
- [sessions/2026-07-13-ai20-gates.md](sessions/2026-07-13-ai20-gates.md) — AI-20's two gates closed: embed-worker decision recorded; eval set hardened (distractors, recall@3) — new baseline recall@3 0.967 / MRR 0.981 / intent 0.955; cutover gate is recall@3+MRR.
- [sessions/2026-07-14-ai20-hybrid-cutover.md](sessions/2026-07-14-ai20-hybrid-cutover.md) — AI-20 shipped + cut over: transactions_v2 (auto-migration), embedding-consumer, hybrid-endpoint (RRF), EsSearch bag SEARCH_BACKEND=es; ES recall@3 0.971 vs chroma 0.967; ChromaDB-sletning venter på bake.
- [sessions/2026-07-15-phase2-wave-b-resume.md](sessions/2026-07-15-phase2-wave-b-resume.md) — rate-limit resume: in-flight wave-B (gateway+user) + P2-14 CI committed & verified; pre-existing user-conftest bug fixed; wave-B scoreboard + remaining plan.

## Templates
- [templates/plan.md](templates/plan.md) · [templates/decision.md](templates/decision.md) · [templates/finding.md](templates/finding.md) · [templates/session.md](templates/session.md)
