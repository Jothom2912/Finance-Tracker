---
title: Refactoring roadmap — production-grade without functional change
date: 2026-07-07
status: open
backlog-items: [P1-01..P1-12, P2-01..P2-20]
related: [../findings/2026-07-07-architecture-audit.md]
---

# Refactoring roadmap

## Goal

Take the codebase from "works in dev" to production-grade on **quality, scalability, maintainability** — with zero functional change. Every phase ships independently and is verified by the existing test suites plus targeted e2e flows.

## Strategy: four phases, strictly ordered

### Phase 1 — Stop the bleeding (P1 items, ~2–3 sessions)
Small, surgical, high-severity fixes: ownership checks (IDOR ×3), fail-closed month close, fail-fast secrets, saga status auth, event-loop unblocking, secrets/PII out of the repo, consumer DLQ, honest saga rollback, gateway pagination. Each is a few files; each gets a regression test. **Do these before anything structural** — they are exploitable/corrupting today and every later refactor would have to carry them along.

Verification per item: service unit tests + a new test reproducing the hole (e.g. cross-user 403 test, close-month-with-upstream-down test).

### Phase 2 — Consolidate the copy-paste layer (P2-01/02/03, the keystone)
Extract into `services/shared/` (the `contracts` package proves the uv path-dependency + Docker COPY mechanism):

1. `shared/messaging`: outbox worker loop, outbox repository, RabbitMQ publisher, consumer base class (DLQ topology, delayed retry to own queue, parse-inside-try, inbox dedup helper, graceful shutdown, logging setup). Parameterized by session factory/Base.
2. `shared/auth`: single JWT validation dependency (claims contract, `require_exp`, fail-fast secret), replacing 9 copies; delete dead `shared/auth/jwt_utils.py`.
3. `shared/domain`: `budget_period.py`, tz-aware `utcnow` helper.

Migration order: start with the two byte-identical copies (user/transaction publisher), then budget/goal (95% identical), then categorization/banking/saga, **account-service last** (divergent rewrite + sync stack). One service per PR; behavior lock = existing worker/consumer tests + e2e event flows (register→default account, tx→categorized, month-close→goal).

This phase makes every later fix (retry hygiene, outbox lifecycle, tz handling) a **single-point change** instead of ×8.

### Phase 3 — Hot-path performance (P2-04..P2-12)
Gateway async + memoization + real pagination end-to-end; import dedup batching + indexes; rules-DB wiring; async EB client; broken caches fixed or removed. These change no responses — verify with recorded-response comparisons (same query, same JSON out) plus load smoke (dashboard with 10k-tx account).

### Phase 4 — Structural consistency (P3)
account-service async migration, RS256/S2S auth (ADR first), legacy budget domain deprecation, event-driven ChromaDB sync, observability, frontend normalization. Each needs its own plan file.

## Non-goals

- No behavior/API changes; no new features; no service boundary redraws.
- No big-bang rewrites — account-service stays sync until Phase 4.

## Risks & rollback

- Shared-package extraction can subtly change worker timing → migrate one service at a time, keep old file until its tests pass against the shared import, then delete.
- Gateway async conversion changes error timing → keep per-client timeout values identical; contract-test the JSON.
- All phases: `make test`, affected-service tests, `make test-e2e` (fix P2-14 first so e2e can actually fail).

## Outcome

_(fill in as phases complete)_
