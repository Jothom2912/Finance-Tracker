Testing goal-service
---------------------

Run unit and integration tests for the goal-service from the repository root.

Makefile (from service folder):

```bash
cd services/goal-service
make test
```

Direct (if you prefer explicit python command):

```bash
PYTHONPATH=".;../shared/contracts" \\
  c:/Users/markx/Documents/GitHub/Finance-Tracker/.venv/Scripts/python.exe -m uv run --active pytest tests/ -q
```
