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

## Patterns (living documents)
- [patterns/README.md](patterns/README.md) — pattern index: table of all patterns with canonical implementations. **Start here for "how do we do X".**
- [patterns/hexagonal-architecture.md](patterns/hexagonal-architecture.md) — layering, ports/adapters, canonical layout; honest enforcement status (archon only in ai+analytics).
- [patterns/transactional-outbox.md](patterns/transactional-outbox.md) — atomic write+event, SKIP LOCKED worker mechanics; user-service is the reference.
- [patterns/idempotent-consumers.md](patterns/idempotent-consumers.md) — inbox dedup, self-healing full-state events, DLQ+retry, consumer anti-patterns.
- [patterns/saga-orchestration.md](patterns/saga-orchestration.md) — orchestrator + command/reply conventions, compensation, honest-failure rule.
- [patterns/cqrs-es-read-store.md](patterns/cqrs-es-read-store.md) — ES read-side (ADR-0004), sole-writer rule, hybrid search, trade-offs.
- [patterns/read-copies-and-denormalization.md](patterns/read-copies-and-denormalization.md) — taxonomy read-copies (ADR-003), denormalized names, cache-not-truth rules.
- [patterns/categorization-pipeline.md](patterns/categorization-pipeline.md) — tier ladder, rule priority ladder 10/50/100, correction feedback loop.
- [patterns/csv-parser-registry.md](patterns/csv-parser-registry.md) — BankCSVParser Protocol + registry, danish-format rules, golden files, adding a bank.
- [patterns/import-dedup.md](patterns/import-dedup.md) — external_id vs fuzzy dedup, three-way rule, accepted gaps (P2-09 digest).
- [patterns/frontend-data-patterns.md](patterns/frontend-data-patterns.md) — TanStack Query + crudFactory house patterns; which CLAUDE.md bits are aspirational.

## Findings
- [findings/2026-07-07-architecture-audit.md](findings/2026-07-07-architecture-audit.md) — full codebase audit: 10 CRITICAL, 27 HIGH, ~45 MEDIUM, ~40 LOW, with file:line evidence.
- [findings/2026-07-12-goal-migration-004-sqlite.md](findings/2026-07-12-goal-migration-004-sqlite.md) — goal migration 004 Postgres-only + fixture migrated wrong DB; resolved 2026-07-17 (F1-04 wave 0).
- [findings/2026-07-17-goal-delete-fk-500.md](findings/2026-07-17-goal-delete-fk-500.md) — goal hard-delete with allocation history → FK 500 (LOW); resolved 2026-07-17 by P3-16 soft-delete.

## Backlog & plans
- [backlog/BACKLOG.md](backlog/BACKLOG.md) — technical backlog (P1 security/money → P2 systemic → P3 consistency), linked to finding IDs. P1 done 2026-07-07.
- [backlog/FEATURES.md](backlog/FEATURES.md) — feature backlog (F1 finish-half-built → F2 high-value → F3 bets), each with existing-scaffolding leverage + prerequisites.
- [backlog/AI-IMPROVEMENTS.md](backlog/AI-IMPROVEMENTS.md) — AI-service ideas: RAG ladder (hybrid search, reranking, multi-hop), router/responder upgrades, eval-first sequencing.
- [backlog/ML-CATEGORIZATION.md](backlog/ML-CATEGORIZATION.md) — ML categorization: getting-started ladder (merchant memory → baseline → shadow mode), feedback flywheel, hierarchical/zero-shot subcategory smarts.
- [plans/2026-07-07-refactoring-roadmap.md](plans/2026-07-07-refactoring-roadmap.md) — 4-phase execution strategy for the technical backlog, with verification approach.
- [plans/2026-07-07-feature-roadmap.md](plans/2026-07-07-feature-roadmap.md) — feature sequencing interleaved with refactor phases + build sketches for the top items.
- [plans/2026-07-11-es-analytics-integration.md](plans/2026-07-11-es-analytics-integration.md) — rebase phase-1-fixes onto master's ES analytics read-side (ADR-0004), bring-up/backfill/dual-read re-verify, + AI-19..21 ES-for-chat proposals.
- [plans/2026-07-12-ai-service-es-chat.md](plans/2026-07-12-ai-service-es-chat.md) — ai-service onto the ES read-store: AI-01 eval gate → AI-19 structured intents → AI-20 hybrid search replaces ChromaDB → AI-21 slots, + cleanup + chat-UI steps.
- [plans/2026-07-17-user-rules-and-feedback-loop.md](plans/2026-07-17-user-rules-and-feedback-loop.md) — F1-02+F1-03: rules CRUD/UI + correction feedback loop (learned corrections stored as auto-managed user rules, priority ladder 10/50/100).
- [plans/2026-07-17-f104-goal-allocation-completion.md](plans/2026-07-17-f104-goal-allocation-completion.md) — F1-04: make the shipped allocation backend reachable — default-goal API, history/unallocated read APIs, close-month button + goals UI.
- [plans/2026-07-17-p316-goal-soft-delete.md](plans/2026-07-17-p316-goal-soft-delete.md) — P3-16: goal soft-delete (deleted_at) fixes FK 500 on delete-with-history; default-flag cleared atomically so the consumer never allocates to a dead goal.
- [plans/2026-07-17-f107-scheduled-month-close.md](plans/2026-07-17-f107-scheduled-month-close.md) — F1-07: day-7 auto-close worker (domain due-rule, repo sweep-query, scheduler container); new trigger only, close semantics untouched.

## Decisions
- [decisions/2026-07-13-embed-worker-placement.md](decisions/2026-07-13-embed-worker-placement.md) — AI-20 embedding writer: separate consumer in analytics-service on own queue `analytics.embeddings`, partial-update of `description_vector`.
- [decisions/2026-07-16-p209-dedup-semantics.md](decisions/2026-07-16-p209-dedup-semantics.md) — P2-09: three-way dedup rule (external_id + in-batch set + NULL-scoped fuzzy fallback), IntegrityError-as-honest-saga-failure, event_version stays 1, accepted transition artifacts.
- [decisions/2026-07-17-learned-corrections-as-rules.md](decisions/2026-07-17-learned-corrections-as-rules.md) — F1-03: corrections stored as auto-managed user rules (priority ladder 10/50/100), not merchant rows; `is_user_confirmed` superseded; consumer cache TTL-only.
- [decisions/2026-07-17-manual-month-close-button.md](decisions/2026-07-17-manual-month-close-button.md) — F1-04: manual "Luk måned"-knap supersedes ADR-0003 out-of-scope; scheduled day-7 close → F1-07.
- [decisions/2026-07-17-scheduler-pattern-worker-loop.md](decisions/2026-07-17-scheduler-pattern-worker-loop.md) — periodic jobs = in-service worker-loop containers (outbox-worker shape), not KEDA cron; idempotency mandatory, single replica, injected clock. F1-07 first user, F1-05 reuses.

## Sessions
- [sessions/2026-07-07-architecture-audit.md](sessions/2026-07-07-architecture-audit.md) — audit session: what was done, method, open ends.
- [sessions/2026-07-07-phase1-p1-fixes.md](sessions/2026-07-07-phase1-p1-fixes.md) — Phase 1: all 12 P1 critical fixes shipped, deploy actions, decisions needed.
- [sessions/2026-07-12-es-integration-rebase.md](sessions/2026-07-12-es-integration-rebase.md) — rebase onto master's ES read-side + stack bring-up: dual-read 0 divergences, backfill, P2-06 crash-loop fixed, Ollama drift fixed.
- [sessions/2026-07-12-ai-es-chat-wave1.md](sessions/2026-07-12-ai-es-chat-wave1.md) — wave 1 of ai-es-chat plan: AI-01 eval harness (baseline 1.000, saturated), AI-19 live-smoked, ports made real, junk deleted; legacy dashboard now deletable.
- [sessions/2026-07-13-gateway-legacy-deletion.md](sessions/2026-07-13-gateway-legacy-deletion.md) — EB active-app vars committed; gateway legacy analytics path + ANALYTICS_READ_SOURCE deleted (ADR-0004 cleanup done, live-smoked); audit's full-history-fetch finding class voided.
- [sessions/2026-07-13-ai20-gates.md](sessions/2026-07-13-ai20-gates.md) — AI-20's two gates closed: embed-worker decision recorded; eval set hardened (distractors, recall@3) — new baseline recall@3 0.967 / MRR 0.981 / intent 0.955; cutover gate is recall@3+MRR.
- [sessions/2026-07-14-ai20-hybrid-cutover.md](sessions/2026-07-14-ai20-hybrid-cutover.md) — AI-20 shipped + cut over: transactions_v2 (auto-migration), embedding-consumer, hybrid-endpoint (RRF), EsSearch bag SEARCH_BACKEND=es; ES recall@3 0.971 vs chroma 0.967; ChromaDB-sletning venter på bake.
- [sessions/2026-07-15-phase2-wave-b-resume.md](sessions/2026-07-15-phase2-wave-b-resume.md) — rate-limit resume: in-flight wave-B (gateway+user) + P2-14 CI committed & verified; pre-existing user-conftest bug fixed; wave-B scoreboard + remaining plan.
- [sessions/2026-07-16-p209-external-id-currency.md](sessions/2026-07-16-p209-external-id-currency.md) — P2-09 shipped in 4 commits: contracts + tx-service dedup/migration 012 + banking producer; Phase 2 code-complete, only P2-15 left; P3-15 found.
- [sessions/2026-07-17-loose-ends-p315-chromadb-secondsync.md](sessions/2026-07-17-loose-ends-p315-chromadb-secondsync.md) — P3-15 chunking shipped; ChromaDB deleted (plan step 12); live second-sync dedup PASSED (214/214 skipped); exam done, EB sandbox PEM gotcha.
- [sessions/2026-07-17-f102-03-wave5-verification.md](sessions/2026-07-17-f102-03-wave5-verification.md) — F1-02/03 wave 5: all suites green, live e2e PASSED (correction→rule ~2s, learned beats seed, KEYWORD post-TTL); root make check local-runnability gotchas.
- [sessions/2026-07-17-f104-goal-allocation.md](sessions/2026-07-17-f104-goal-allocation.md) — F1-04 shipped in 4 commits: default-goal API + read APIs + UI + close-knap; live e2e PASSED (goal +150 på ~2s, unallocated, 409); spawned F1-07 + P3-16.
- [sessions/2026-07-17-p316-goal-soft-delete.md](sessions/2026-07-17-p316-goal-soft-delete.md) — P3-16 shipped: goal soft-delete (migration 005), delete-with-history 500→204, live e2e PASSED; sqlite-FK-pragma gotcha.
- [sessions/2026-07-17-f107-scheduled-month-close.md](sessions/2026-07-17-f107-scheduled-month-close.md) — F1-07 shipped: day-7 auto-close worker + scheduler-pattern decision; live e2e PASSED (auto-close +120, manual-close skip, idempotent tick); sqlite-create_all + PYTHONPATH gotchas.

## Templates
- [templates/plan.md](templates/plan.md) · [templates/decision.md](templates/decision.md) · [templates/finding.md](templates/finding.md) · [templates/session.md](templates/session.md)
