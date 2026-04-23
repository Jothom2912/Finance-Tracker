# ADR-002: Categories ownership retained in transaction-service during phase 1

## Status

Accepted — temporary technical debt

## Context

Phase 1 of the categorization extraction is complete: categorization-service
owns taxonomy (subcategories, merchants), rules, the rule engine, and the
categorization pipeline. But CRUD endpoints for top-level categories still
live in transaction-service, which also emits `category.*` events.

Transferring ownership involves changes in 3-4 other components (frontend
URL routing, budget-service consumer rewiring, monolith CategorySyncConsumer
re-pointing, shared contracts). That is a cross-cutting change that should
not hang on the end of a migration that has already delivered its main value.

## Decision

Defer transfer of categories CRUD ownership to categorization-service as a
separate epic.

In the meantime, categorization-service runs a `CategorySyncConsumer` that
listens to `category.*` events from transaction-service and keeps its local
categories table synchronized. This prevents data divergence while the dual
ownership persists.

## Consequences

**Positive:**
- Phase 1 completes without scope creep
- Frontend, budget-service, and monolith are unaffected
- Cat-service's categories table stays in sync via events

**Negative:**
- Dual-ownership anti-pattern accepted temporarily
- Category CRUD API exists in two services (cat-service endpoints disabled
  to prevent split-brain — see below)
- Developers must understand that transaction-service is authoritative for
  categories until this ADR is superseded

**Mitigation:**
- Cat-service's `category_api.py` CRUD endpoints are disabled (not registered
  in `main.py`) to prevent accidental writes to the non-authoritative copy
- `CategorySyncConsumer` keeps cat-service's read copy synchronized
- This ADR documents the decision and exit criteria

## Exit Criteria

Transfer is planned as a separate epic when any of:

1. Next major feature touches categories (natural opportunity to rewire)
2. Frontend is refactored (URLs change anyway)
3. Budget-service extraction begins (consumer rewiring is already in scope)

## Supersedes

None (first ADR on this topic).
