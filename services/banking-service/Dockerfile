FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:0.6 /uv /uvx /usr/local/bin/

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1 \
    PATH="/app/.venv/bin:$PATH"

# P3-23: shared/* land in /shared, not under /app, because pyproject declares them
# as `path = "../shared/auth"` — relative to /app/pyproject.toml that resolves here.
# Three packages, not budget's four: banking does not import `domain`.
COPY services/shared/contracts /shared/contracts
COPY services/shared/auth /shared/auth
COPY services/shared/messaging /shared/messaging
COPY services/shared/observability /shared/observability

COPY services/banking-service/pyproject.toml services/banking-service/uv.lock ./
RUN uv sync --frozen --no-dev

COPY services/banking-service/app/ ./app/
COPY services/banking-service/migrations/ ./migrations/
COPY services/banking-service/alembic.ini ./

RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8009

# The venv is on PATH, so the four workers' `command: ["python", "-m", ...]` in
# docker-compose.yml (banking-outbox-worker, banking-account-projection-consumer,
# banking-saga-command-consumer, banking-sync-scheduler) resolve to
# /app/.venv/bin/python. Dropping PATH here would leave all four on the system
# interpreter with no dependencies installed — while this CMD's API still answers
# 200, which is why the verification reads the workers' logs and not just /health.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8009"]
