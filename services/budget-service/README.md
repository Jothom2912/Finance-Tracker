# Budget Service (Planned)

**Status: Not yet implemented.** Budget management is currently handled by the monolith on port 8000.

This service will manage budgets, monthly budgets, and budget lines when extracted.

## Planned Port

```
8003
```

## Current Location

Budget logic currently lives in:
- `backend/budget/` — legacy per-category budgets
- `backend/monthly_budget/` — aggregate-based monthly budgets with budget lines
