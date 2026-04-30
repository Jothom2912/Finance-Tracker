FROM ghcr.io/astral-sh/uv:0.6 AS builder

WORKDIR /app
COPY services/shared/contracts /shared/contracts
COPY services/goal-service/pyproject.toml /app/pyproject.toml
RUN uv sync --frozen --no-dev

COPY services/goal-service/app /app/app
COPY services/goal-service/migrations /app/migrations
COPY services/goal-service/alembic.ini /app/alembic.ini

FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /app /app
ENV PYTHONPATH=/app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8003"]
