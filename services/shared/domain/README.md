# finans-tracker-domain

Shared, transport-agnostic domain logic used by multiple services.
Currently contains a single module: the **budget period calculator**
(`domain.budget_period`), consolidating the near-identical copies in
budget-service, gateway-service, account-service and analytics-service.

Pure functions only — no dependencies, no I/O, no framework imports.
Anything added here must stay that way (this is the shared *domain*
layer; adapters and infrastructure belong elsewhere).

## Install

```toml
dependencies = [
    "finans-tracker-domain",
]

[tool.uv.sources]
finans-tracker-domain = { path = "../shared/domain" }
```

## Usage

```python
from domain import budget_period, determine_budget_month

# Budget "April 2026" with start_day=28 → (date(2026, 3, 28), date(2026, 4, 27))
start, end = budget_period(2026, 4, start_day=28)

# Which budget month does a transaction on 2026-03-30 belong to (start_day=28)?
year, month = determine_budget_month(date(2026, 3, 30), start_day=28)  # (2026, 4)
```

Semantics:

- The budget month label `(year, month)` refers to the month that
  contains the **end** of the period. With `start_day=1` it is the
  plain calendar month.
- `start_day` is clamped to 1–28 (every month has at least 28 days);
  out-of-range values are clamped silently. `MIN_START_DAY` /
  `MAX_START_DAY` are exported.
- Both endpoints of the returned range are **inclusive**.

## Architecture

```text
domain/
└── budget_period.py  # budget_period, determine_budget_month, MIN_START_DAY, MAX_START_DAY
```

## Migration

See `MIGRATION.md` for the per-service adoption recipe, including which
service-local additions (e.g. analytics-service's
`histogram_bucket_to_budget_month` / `months_in_period`) must be
preserved locally.

## Testing

```bash
cd services/shared/domain
uv sync --extra dev
uv run pytest
```
