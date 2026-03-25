FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:0.6 /uv /uvx /usr/local/bin/

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

COPY services/shared/contracts /shared/contracts

COPY services/user-service/pyproject.toml services/user-service/uv.lock ./
RUN uv sync --frozen --no-dev

COPY services/user-service/app/ ./app/
COPY services/user-service/migrations/ ./migrations/
COPY services/user-service/alembic.ini ./
RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8001

CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8001"]
