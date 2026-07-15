FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:0.6 /uv /uvx /usr/local/bin/

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONPATH="/app" \
    PATH="/app/.venv/bin:$PATH"

# Shared packages resolve via the relative paths recorded in uv.lock
# (../shared/<pkg> from /app -> /shared/<pkg>). Requires repo-root build
# context — never build with the service directory as context.
COPY services/shared/auth /shared/auth
COPY services/shared/domain /shared/domain
COPY services/gateway-service/pyproject.toml services/gateway-service/uv.lock ./
RUN uv sync --frozen --no-dev

COPY services/gateway-service/app ./app

EXPOSE 8010

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8010"]
