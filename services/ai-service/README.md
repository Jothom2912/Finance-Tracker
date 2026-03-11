# AI / Categorization Service (Planned)

**Status: Not yet implemented.** Transaction categorization is not yet automated.

This service will provide AI-powered transaction categorization using a tiered approach: rule-based, ML model, and LLM fallback (Claude/Ollama) with confidence scoring.

## Planned Port

```
8005
```

## Planned Event Flow

- Listens for `transaction.created` events
- Categorizes the transaction
- Publishes `transaction.categorized` event
