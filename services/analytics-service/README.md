# Analytics Service (Planned)

**Status: Not yet implemented.** Analytics and the GraphQL read gateway are currently handled by the monolith on port 8000.

This service will provide dashboard analytics, reporting, data aggregation, and the GraphQL gateway when extracted. Planned to use Elasticsearch for denormalized read views.

## Planned Port

```
8004
```

## Current Location

Analytics logic currently lives in:
- `backend/analytics/` — dashboard overview, expenses-by-month, GraphQL read gateway
