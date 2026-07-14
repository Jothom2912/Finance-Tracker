# Adopting finans-tracker-domain in a service

A mechanical, per-service recipe. The mechanics copy the already-adopted
`finans-tracker-contracts` pattern exactly (reference:
`services/goal-service/pyproject.toml` + `Dockerfile`).

Known local copies of `budget_period`:

- `services/budget-service/app/domain/budget_period.py`
- `services/gateway-service/app/shared/budget_period.py`
- `services/account-service/app/shared/budget_period.py`
- `services/analytics-service/app/domain/budget_period.py` (extended —
  see divergence #1)

## 1. pyproject.toml

```toml
[project]
dependencies = [
    # ...existing...
    "finans-tracker-domain",
]

[tool.uv.sources]
finans-tracker-domain = { path = "../shared/domain" }
```

Then, from the service directory:

```bash
uv lock
uv sync
```

The lock records `source = { directory = "../shared/domain" }`. The
package has zero runtime dependencies, so resolution changes nothing
else. uv does not content-hash directory sources; later shared edits do
not invalidate the lockfile.

## 2. Dockerfile

Add before the `uv sync --frozen` layer:

```dockerfile
COPY services/shared/domain /shared/domain
COPY services/<svc>/pyproject.toml services/<svc>/uv.lock ./
RUN uv sync --frozen --no-dev
```

`WORKDIR` is `/app`, so the recorded relative path `../shared/domain`
resolves to `/shared/domain` in the container.

**Build-context caveat:** `COPY services/shared/...` requires the
repo-root build context (`context: .` in docker-compose.yml, with
`dockerfile: services/<svc>/Dockerfile`). Never build with the service
directory as context.

## 3. Import swap

| Old (service-local) | New (shared) |
|---|---|
| `from app.domain.budget_period import budget_period, determine_budget_month` (budget-, analytics-service) | `from domain import budget_period, determine_budget_month` |
| `from app.shared.budget_period import ...` (gateway-, account-service) | `from domain import ...` |
| local `MIN_START_DAY` / `MAX_START_DAY` constants | `from domain import MIN_START_DAY, MAX_START_DAY` |

Public API (pure functions, identical signatures to every local copy):

```python
budget_period(year: int, month: int, start_day: int) -> tuple[date, date]
    # inclusive (start_date, end_date); label = month containing the END

determine_budget_month(tx_date: date, start_day: int) -> tuple[int, int]

MIN_START_DAY = 1
MAX_START_DAY = 28   # start_day silently clamped to this range
```

Note the top-level package name is `domain` — if a service's own code
uses a top-level module literally named `domain` (none do today; they
all use `app.domain.*`), there would be a collision. Check before
adopting in a new service.

Hexagonal note: `domain` is dependency-free and may be imported from
the service's domain layer. If pytest-archon rules whitelist imports,
add `domain` to the allowed list for the domain layer.

## 4. Delete after adoption

- `app/domain/budget_period.py` or `app/shared/budget_period.py`
  (budget-, gateway-, account-service: the entire file — the copies are
  functionally identical to the shared code, only docstrings differ;
  analytics-service: only the shared functions — see divergence #1)
- the local copy's unit tests (the package carries 35 tests, superset
  incl. leap years, clamping, year boundaries); keep any service tests
  that exercise service behavior *through* these functions

## 5. Divergence warnings (found by sampling, 2026-07-14)

1. **analytics-service's copy is extended, not identical**
   (`services/analytics-service/app/domain/budget_period.py`, 82
   lines). On top of the shared functions it defines:
   - `histogram_bucket_to_budget_month(bucket_start: date, start_day: int) -> str`
     — maps an ES `date_histogram` bucket start (offset
     `+(start_day-1)d`) to a `"YYYY-MM"` budget-month label; and
   - `months_in_period(start_date, end_date) -> float` — deliberately
     replicates the gateway's averaging formula for dual-read
     comparison of `average_monthly_expenses`.

   Both are analytics-specific and **must be preserved locally**. Slim
   the local file down to these two functions importing
   `determine_budget_month` from `domain` — do not delete the file.

2. **budget-service vs gateway-service copies are functionally
   identical** to the shared package (diff shows docstring/comment
   differences only), as is account-service's. Straight swap.

3. **Behavioral note, not a divergence**: MEMORY records a
   "forbrug vs. budget mismatch" where budget-service diverges from the
   gateway/analytics read-side. That divergence lives in *how the
   services use* period math (which dates they feed it), not in
   `budget_period` itself — adopting the shared package will NOT fix
   it, and adopting is safe regardless.

## 6. Verification checklist

- [ ] `uv lock && uv sync` succeeds; only the new package in the diff
- [ ] Service test suite green (`uv run pytest`)
- [ ] `uv run ruff check .` clean
- [ ] `docker compose build <svc>` succeeds (repo-root context)
- [ ] Spot-check one non-trivial period through the service API, e.g.
      budget "April" with `start_day=28` must span Mar 28 – Apr 27
      (both inclusive), and a transaction on the 28th must land in the
      *next* budget month
