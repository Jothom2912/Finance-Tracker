---
title: Patterns — index
updated: 2026-07-17
source: distilled from architecture docs + decisions + CLAUDE.md conventions
---

# Patterns

One file per recurring pattern: what it is, why we use it, where the **canonical
implementation** lives, and the known gotchas. These are living documents — update them
when a pattern changes, and link new decisions/findings back here.

Reading order for a newcomer: hexagonal → outbox → idempotent consumers → saga, then the
domain-specific ones.

| Pattern | One-liner | Canonical implementation |
|---|---|---|
| [Hexagonal architecture](hexagonal-architecture.md) | Ports/adapters layering per service; domain free of infrastructure | user-service (cleanest), ai-service (enforced by tests) |
| [Transactional outbox](transactional-outbox.md) | Domain write + event row in one commit; worker publishes | user-service (reference impl) |
| [Idempotent consumers](idempotent-consumers.md) | Inbox dedup, full-state ("self-healing") events, DLQ + retry | goal-service (best consumer), transaction-service (inbox) |
| [Saga orchestration](saga-orchestration.md) | Generic orchestrator + command/reply over the topic exchange | saga-service + bank_sync saga |
| [CQRS / ES read-store](cqrs-es-read-store.md) | Writes on domain services; reads pre-aggregated from Elasticsearch via gateway BFF | analytics-service + gateway (ADR-0004) |
| [Read-copies & denormalization](read-copies-and-denormalization.md) | Owned data replicated via full-state events; names denormalized onto rows | taxonomy: categorization → transaction-service (ADR-003) |
| [Categorization pipeline](categorization-pipeline.md) | Tiered rules engine with user/learned rule priority ladder + correction feedback loop | categorization-service |
| [CSV parser registry](csv-parser-registry.md) | Protocol + registry per bank format (Open/Closed) | transaction-service `csv_parsers/` |
| [Import dedup](import-dedup.md) | `(account_id, external_id)` for bank imports, fuzzy key fallback for CSV | transaction-service `bulk_import` (P2-09) |
| [Frontend data layer](frontend-data-patterns.md) | TanStack Query + crudFactory + key factories; no Redux | `features/chat/` (best slice), `api/crudFactory.jsx` |

## Conventions for these docs

- Treat file paths as claims with a date (`updated:` frontmatter) — verify before relying.
- When a pattern is **aspirational** (in CLAUDE.md but not uniformly implemented), the doc
  says so explicitly — do not "fix" code to match a doc without checking the backlog first.
- New pattern → new file here + one line in this table + one line in
  [00-INDEX.md](../00-INDEX.md).
