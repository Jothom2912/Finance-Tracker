FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:0.6 /uv /uvx /usr/local/bin/

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

# P2-37: shared/* land in /shared, not under /app, because pyproject declares them
# as `path = "../shared/auth"` — relative to /app/pyproject.toml that resolves here.
# Four packages, not the three transaction-service copies: budget also uses domain.
COPY services/shared/contracts /shared/contracts
COPY services/shared/auth /shared/auth
COPY services/shared/messaging /shared/messaging
COPY services/shared/domain /shared/domain
COPY services/shared/observability /shared/observability

COPY services/budget-service/pyproject.toml services/budget-service/uv.lock ./
RUN uv sync --frozen --no-dev

COPY services/budget-service/app/ ./app/
COPY services/budget-service/migrations/ ./migrations/
COPY services/budget-service/alembic.ini ./

RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8003

# The venv is on PATH, so the three workers' `command: ["python", "-m", ...]` in
# docker-compose.yml resolve to /app/.venv/bin/python. Dropping PATH here would leave
# them on the system interpreter with no dependencies installed.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8003"]
