# Session logs

One line per session, newest first. These are a record of *how* work went — what
surprised us, what turned out wrong — not a source of architecture facts. Read a
specific one when you need the story behind a change; do not load this file as
context by default. Add a line here (not to `00-INDEX.md`) for every new log.

- [sessions/2026-07-28-p324-datastore-loopback.md](2026-07-28-p324-datastore-loopback.md) — P3-24's datastore-halvdel shipped: 14 mappings på `127.0.0.1`, 14/14 → 0/14 LAN-nåelige og 642 transaktions-docs var faktisk læsbare uden auth før; backloggens "no downside" holdt kun for loopback-bind, og pipe-fælden ramte selve kontrollen (6. gang).
- [sessions/2026-07-28-p229-csv-upload-guards.md](2026-07-28-p229-csv-upload-guards.md) — P2-29 shipped: byte-/række-/transportgrænse på `/import-csv`, OOM'en bevist virkelig (`OOMKilled=137` med guarden slået fra via env); planens `du`-måling var et forkert instrument, fordi `tempfile` bruger `O_TMPFILE` — `df` viste de 137 MB `du` ikke kunne se.
- [sessions/2026-07-28-p323-banking-uv-pyproject.md](2026-07-28-p323-banking-uv-pyproject.md) — P3-23 shipped: banking på uv + pyproject + typecheck-gaten (11/12 install-sti, 9/12 gate); `python-jose`'s to CVE'er sad i imaget for én tests skyld, og gaten genopdagede fire kendte kontrakt-items frem for at finde nye bugs.
- [sessions/2026-07-28-p237-single-install-path.md](2026-07-28-p237-single-install-path.md) — P2-37 shipped: budgets image læser `uv.lock` (10/12 services nu); den httpx-bump ingen test kunne dække blev verificeret gratis af en workers egne logs, og redis-risikoen skrumpede fordi cachen viste sig ubrugt (→ P3-42).
- [sessions/2026-07-27-p231-typecheck-gate.md](2026-07-27-p231-typecheck-gate.md) — P2-31 shipped: mypy hård gate på 8/12 services; udbyttet var fem usande kontrakter, ikke typefejl (→ P2-32…P2-37).
- [sessions/2026-07-27-p340-worker-image-sharing.md](2026-07-27-p340-worker-image-sharing.md) — P3-40 shipped: 26 workers deler API-imaget; A/B bevist (samme kommandoer: 0 markør-hits på gammel compose, 1 på ny).
- [sessions/2026-07-27-p115-p226-and-notes-infra.md](2026-07-27-p115-p226-and-notes-infra.md) — P1-15/P2-26 shipped (categorize-auth, nøglerotation, `exp` i 12 services) + dev-notes gjort maskin-checkbar (`make notes-check`, STATUS.md indført).
- [sessions/2026-07-26-p320-cleanup-script-outbox.md](2026-07-26-p320-cleanup-script-outbox.md) — P3-20 shipped: ES juli 17.666,17 → 17.528,17 (= Postgres eksakt), 0 fantomer tilbage for rigtige brugere.
- [sessions/2026-07-26-product-surface-sweep.md](2026-07-26-product-surface-sweep.md) — documentation-only sweep of what the backlog was not looking at.
- [sessions/2026-07-26-p114-transaction-list-pagination.md](2026-07-26-p114-transaction-list-pagination.md) — P1-14 shipped: transaktionslisten pages hele perioden med `{total_count, items}` (juni 93, målt = Postgres = analytics 16 709,83).
- [sessions/2026-07-25-notification-hardening-and-p222.md](2026-07-25-notification-hardening-and-p222.md) — hardening-close-out + P2-22: saga-kommandoer kan ikke dedupes på `correlation_id` (samme for alle trin) → `(saga_id, step_name)`.
- [sessions/2026-07-25-p113-budget-spend-from-analytics.md](2026-07-25-p113-budget-spend-from-analytics.md) — P1-13 shipped: forbrug fra analytics (juni 5.180,32 → 16.739,83); fail-closed live-verificeret.
- [sessions/2026-07-25-loose-ends-cleanup.md](2026-07-25-loose-ends-cleanup.md) — dev-artefakter + 2 DLQ'er ryddet; 3 utrackede fund skrevet op (P1-13 budget-trunkering, P2-25 hard-delete, P3-19 poison).
- [sessions/2026-07-20-f101-notification-service.md](2026-07-20-f101-notification-service.md) — F1-01 shipped: notification-service (stub→hexagonal, 3 triggers, REST feed + bell UI); live e2e PASSED all 3.
- [sessions/2026-07-20-f203-mid-month-budget-alerts.md](2026-07-20-f203-mid-month-budget-alerts.md) — F2-03 shipped: budget-alert-scheduler → `budget.line_threshold_crossed` (80/100) → notification-service 4th trigger; live e2e PASSED 4/4.
- [sessions/2026-07-17-loose-ends-p315-chromadb-secondsync.md](2026-07-17-loose-ends-p315-chromadb-secondsync.md) — P3-15 chunking shipped; ChromaDB deleted (plan step 12); live second-sync dedup PASSED (214/214 skipped); exam done, EB sandbox PEM gotcha.
- [sessions/2026-07-17-f102-03-wave5-verification.md](2026-07-17-f102-03-wave5-verification.md) — F1-02/03 wave 5: all suites green, live e2e PASSED (correction→rule ~2s, learned beats seed, KEYWORD post-TTL).
- [sessions/2026-07-17-f104-goal-allocation.md](2026-07-17-f104-goal-allocation.md) — F1-04 shipped in 4 commits: default-goal API + read APIs + UI + close-knap; live e2e PASSED (goal +150 på ~2s, unallocated, 409).
- [sessions/2026-07-17-p316-goal-soft-delete.md](2026-07-17-p316-goal-soft-delete.md) — P3-16 shipped: goal soft-delete (migration 005), delete-with-history 500→204, live e2e PASSED; sqlite-FK-pragma gotcha.
- [sessions/2026-07-17-f107-scheduled-month-close.md](2026-07-17-f107-scheduled-month-close.md) — F1-07 shipped: day-7 auto-close worker + scheduler-pattern decision; live e2e PASSED (auto-close +120, manual-close skip, idempotent tick).
- [sessions/2026-07-17-p314-sync-claim.md](2026-07-17-p314-sync-claim.md) — P3-14 shipped: in-flight sync-claim (design-pivot fra deterministisk correlation-id); live e2e PASSED (concurrent → samme saga_id, claim roterer).
- [sessions/2026-07-17-f105-scheduled-sync.md](2026-07-17-f105-scheduled-sync.md) — F1-05 shipped: nightly sync-scheduler; live e2e PASSED (auto-saga, scheduler deferred til manuel saga, 0 due på prod-config).
- [sessions/2026-07-16-p209-external-id-currency.md](2026-07-16-p209-external-id-currency.md) — P2-09 shipped in 4 commits: contracts + tx-service dedup/migration 012 + banking producer; Phase 2 code-complete, only P2-15 left; P3-15 found.
- [sessions/2026-07-15-phase2-wave-b-resume.md](2026-07-15-phase2-wave-b-resume.md) — rate-limit resume: in-flight wave-B (gateway+user) + P2-14 CI committed & verified; pre-existing user-conftest bug fixed.
- [sessions/2026-07-14-ai20-hybrid-cutover.md](2026-07-14-ai20-hybrid-cutover.md) — AI-20 shipped + cut over: transactions_v2 (auto-migration), embedding-consumer, hybrid-endpoint (RRF), EsSearch bag SEARCH_BACKEND=es.
- [sessions/2026-07-13-gateway-legacy-deletion.md](2026-07-13-gateway-legacy-deletion.md) — EB active-app vars committed; gateway legacy analytics path + ANALYTICS_READ_SOURCE deleted (ADR-0004 cleanup done, live-smoked).
- [sessions/2026-07-13-ai20-gates.md](2026-07-13-ai20-gates.md) — AI-20's two gates closed: embed-worker decision recorded; eval set hardened (distractors, recall@3).
- [sessions/2026-07-12-es-integration-rebase.md](2026-07-12-es-integration-rebase.md) — rebase onto master's ES read-side + stack bring-up: dual-read 0 divergences, backfill, P2-06 crash-loop fixed, Ollama drift fixed.
- [sessions/2026-07-12-ai-es-chat-wave1.md](2026-07-12-ai-es-chat-wave1.md) — wave 1 of ai-es-chat plan: AI-01 eval harness (baseline 1.000, saturated), AI-19 live-smoked, ports made real, junk deleted.
- [sessions/2026-07-07-architecture-audit.md](2026-07-07-architecture-audit.md) — audit session: what was done, method, open ends.
- [sessions/2026-07-07-phase1-p1-fixes.md](2026-07-07-phase1-p1-fixes.md) — Phase 1: all 12 P1 critical fixes shipped, deploy actions, decisions needed.
- [sessions/2026-07-07-phase2-in-flight.md](2026-07-07-phase2-in-flight.md) — Phase 2 interrupted mid-flight: verified on-disk state (compile + shared-package suites) + resume procedure per service.
