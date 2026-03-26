# AI / Categorization Service (Planned Extraction)

**Status: Partially implemented in monolith.** The categorization pipeline is built and running inside the monolith (`backend/category/`). Extraction to a standalone service is planned for a future phase.

## What is already implemented (in monolith)

The monolith contains a complete multi-tier categorization pipeline:

1. **Rule Engine** — Keyword-based matching with longest-match-first strategy and sign-dependent overrides. Uses a three-level hierarchy: Category, SubCategory, Merchant.
2. **ML Categorizer** — Port defined (`IMlCategorizer` protocol), adapter not yet implemented.
3. **LLM Categorizer** — Port defined (`ILlmCategorizer` protocol), adapter not yet implemented.
4. **Fallback** — Default "Ovrigt" subcategory when no tier matches.

Each transaction stores `categorization_tier` ("rule", "ml", "llm", "fallback") and `categorization_confidence` for observability.

### Current hit rate (Nordea sandbox, 267 transactions)

- Rule engine: ~39% auto-categorized
- Fallback: ~61% (awaiting ML/LLM adapters)

## Current Location

Categorization logic currently lives in:
- `services/monolith/backend/category/application/categorization_service.py` — Multi-tier orchestrator
- `services/monolith/backend/category/adapters/outbound/rule_engine.py` — Rule engine
- `services/monolith/backend/category/application/ports/outbound.py` — `IRuleEngine`, `IMlCategorizer`, `ILlmCategorizer` protocols
- `services/monolith/backend/category/domain/value_objects.py` — `CategorizationTier`, `CategorizationResult`

## Planned Port (when extracted)

```
8005
```

## Planned Event Flow (when extracted)

- Listens for `transaction.created` events
- Categorizes the transaction using rule/ML/LLM pipeline
- Publishes `transaction.categorized` event
