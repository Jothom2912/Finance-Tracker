FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:0.6 /uv /uvx /usr/local/bin/

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

COPY services/shared/contracts /shared/contracts

COPY services/categorization-service/pyproject.toml services/categorization-service/uv.lock ./
RUN uv sync --frozen --no-dev

COPY services/categorization-service/app/ ./app/
COPY services/categorization-service/migrations/ ./migrations/
COPY services/categorization-service/alembic.ini ./
RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8005

CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8005"]
