# Testing goal-service

Run unit and integration tests for the goal-service.

## Via Makefile (recommended)

```bash
cd services/goal-service
make test
```

## Quality checks

```bash
cd services/goal-service
make check
```

## Direct pytest

```bash
cd services/goal-service
uv run pytest tests/ -q
```

## Notes

- `tests/conftest.py` sets safe defaults for local test execution (in-memory SQLite).
- The service expects `JWT_SECRET` and `DATABASE_URL` in real deployments.
