# AI / Categorization Service

**Status: Rule-based pipeline extracted to `services/categorization-service` (port `8005`).** ML/LLM adapters remain planned extensions.

## What is implemented

### Categorization-service (port 8005)

The standalone categorization-service owns the full categorization domain:

1. **Taxonomy**: Categories, subcategories, merchants (7 Postgres tables)
2. **Rule Engine**: Keyword-based matching with longest-match-first strategy, sign-dependent overrides, Danish character normalization
3. **Categorization Pipeline Orchestrator**: Rules, ML (port defined), LLM (port defined), fallback
4. **Sync HTTP endpoint**: `POST /api/v1/categorize/` for tier 1 rule engine (called by transaction-service with 500ms timeout)
5. **Async consumer**: Listens for `transaction.created` events, runs full pipeline, publishes `transaction.categorized`
6. **Category sync consumer**: Listens for `category.*` events from transaction-service to keep local taxonomy in sync

See `services/categorization-service/docs/SCHEMA.md` for the database schema and `services/categorization-service/docs/RETROSPECTIVE.md` for the extraction retrospective.

### Monolith (dual-run, pending removal)

The monolith's `BankingService` still runs its local rule engine before sending transactions to transaction-service. The categorization-service's async pipeline overwrites the result. Both produce the same output (1:1 port), so the dual-run is a no-op in practice. Removal is tracked as technical debt (see RETROSPECTIVE.md, section "Deferred as Technical Debt").

Monolith categorization code:
- `services/monolith/backend/category/application/categorization_service.py` — Multi-tier orchestrator
- `services/monolith/backend/category/adapters/outbound/rule_engine.py` — Rule engine
- `services/monolith/backend/category/application/ports/outbound.py` — `IRuleEngine`, `IMlCategorizer`, `ILlmCategorizer` protocols

## Port

```
8005
```

## Event Flow

- Listens for `transaction.created` events (async full pipeline)
- Categorizes using rule engine, ML (future), LLM (future), fallback
- Publishes `transaction.categorized` event
- Listens for `category.*` events (keeps local taxonomy in sync)

## Current hit rate (baseline from 2026-04-22)

- Rule engine: ~77% auto-categorized
- Fallback: ~23% (N=205)

See `docs/categorization-baseline.md` for the measurement methodology and decision thresholds.

## Planned extensions

- **ML categorizer adapter**: Train on user-confirmed merchants via fastText or BERT-Danish
- **LLM categorizer adapter**: GPT/Claude for unknown transactions
- **User-specific rules**: Schema supports `user_id` on rules; API and UI not yet built
