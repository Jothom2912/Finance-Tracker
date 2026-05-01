# AI / Categorization Service

**Status: Extracted as `services/categorization-service` on port `8005`.** The rule-based pipeline now runs as a standalone service. ML/LLM adapters remain planned extensions.

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

## Port

```
8005
```

## Event Flow

- Listens for `transaction.created` events
- Categorizes the transaction using rule/ML/LLM pipeline
- Publishes `transaction.categorized` event
