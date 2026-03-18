FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:0.6 /uv /uvx /usr/local/bin/

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY services/shared/contracts /shared/contracts

COPY services/transaction-service/pyproject.toml services/transaction-service/uv.lock ./
RUN uv sync --frozen --no-dev

COPY services/transaction-service/app/ ./app/
COPY services/transaction-service/migrations/ ./migrations/
COPY services/transaction-service/alembic.ini ./

RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8002

CMD ["/app/.venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]
