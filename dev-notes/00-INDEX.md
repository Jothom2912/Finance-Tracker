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

## Backlog & plans
- [backlog/BACKLOG.md](backlog/BACKLOG.md) — technical backlog (P1 security/money → P2 systemic → P3 consistency), linked to finding IDs. P1 done 2026-07-07.
- [backlog/FEATURES.md](backlog/FEATURES.md) — feature backlog (F1 finish-half-built → F2 high-value → F3 bets), each with existing-scaffolding leverage + prerequisites.
- [backlog/AI-IMPROVEMENTS.md](backlog/AI-IMPROVEMENTS.md) — AI-service ideas: RAG ladder (hybrid search, reranking, multi-hop), router/responder upgrades, eval-first sequencing.
- [backlog/ML-CATEGORIZATION.md](backlog/ML-CATEGORIZATION.md) — ML categorization: getting-started ladder (merchant memory → baseline → shadow mode), feedback flywheel, hierarchical/zero-shot subcategory smarts.
- [plans/2026-07-07-refactoring-roadmap.md](plans/2026-07-07-refactoring-roadmap.md) — 4-phase execution strategy for the technical backlog, with verification approach.
- [plans/2026-07-07-feature-roadmap.md](plans/2026-07-07-feature-roadmap.md) — feature sequencing interleaved with refactor phases + build sketches for the top items.
- [plans/2026-07-11-es-analytics-integration.md](plans/2026-07-11-es-analytics-integration.md) — rebase phase-1-fixes onto master's ES analytics read-side (ADR-0004), bring-up/backfill/dual-read re-verify, + AI-19..21 ES-for-chat proposals.

## Decisions
- (none yet — formal ADRs live in `docs/adr/`; log day-to-day decisions here via the `dev-notes-decision` skill)

## Sessions
- [sessions/2026-07-07-architecture-audit.md](sessions/2026-07-07-architecture-audit.md) — audit session: what was done, method, open ends.
- [sessions/2026-07-07-phase1-p1-fixes.md](sessions/2026-07-07-phase1-p1-fixes.md) — Phase 1: all 12 P1 critical fixes shipped, deploy actions, decisions needed.
- [sessions/2026-07-12-es-integration-rebase.md](sessions/2026-07-12-es-integration-rebase.md) — rebase onto master's ES read-side + stack bring-up: dual-read 0 divergences, backfill, P2-06 crash-loop fixed, Ollama drift fixed.

## Templates
- [templates/plan.md](templates/plan.md) · [templates/decision.md](templates/decision.md) · [templates/finding.md](templates/finding.md) · [templates/session.md](templates/session.md)
