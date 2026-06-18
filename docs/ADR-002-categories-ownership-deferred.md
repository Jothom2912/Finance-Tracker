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
- Category write API previously existed in two services; cat-service's write
  routes have now been removed to prevent split-brain (see Mitigation)
- Developers must understand that transaction-service is authoritative for
  categories until this ADR is superseded

**Mitigation:**
- Cat-service's `category_api.py` **write** routes (POST/PUT/DELETE) are
  removed so transaction-service is the sole writer to the categories table.
  (Historical note: this mitigation was documented here but not actually
  implemented — the full `category_router` was still registered in `main.py`.
  The "category-consistency / Fase 1" change corrected code to match this ADR.)
- Cat-service's category **read** routes (`GET /`, `GET /{id}`,
  `GET /{id}/subcategories`) are intentionally kept, because budget-service's
  `CategoryPort` reads category existence and names from cat-service. Removing
  them would silently degrade budget-service (its graceful fallback would mask
  the regression). See NOTE below.
- `CategorySyncConsumer` keeps cat-service's read copy synchronized
- This ADR documents the decision and exit criteria

## NOTE: parent categories are read from two services (discovered during Fase 1)

Parent categories are currently **read** from two different services:

- **frontend** and **gateway-service** read categories from **transaction-service**
  (`http://transaction-service:8002/api/v1/categories`).
- **budget-service** reads categories from **categorization-service**
  (`CATEGORY_SERVICE_URL = http://categorization-service:8005/api/v1/categories`,
  via `CategoryPort.exists/get_name/get_all_names`).

So even the *read* path lacks a single source of truth. This is tolerated for
now: both copies are kept consistent by `CategorySyncConsumer`, and writes are
funnelled through transaction-service only (after Fase 1).

Full consolidation — making **categorization-service** the single owner of the
entire taxonomy (parents + subcategories) with transaction-service holding only
references — is **decision A** and a separate, larger epic that belongs **after
the exam**. It touches frontend URL routing, budget-service wiring, and the
shared contracts, so it must not be bundled into the category-consistency fix.
No consolidation code changes are made now.

## Exit Criteria

Transfer is planned as a separate epic when any of:

1. Next major feature touches categories (natural opportunity to rewire)
2. Frontend is refactored (URLs change anyway)
3. Budget-service extraction begins (consumer rewiring is already in scope)

## Supersedes

None (first ADR on this topic).
