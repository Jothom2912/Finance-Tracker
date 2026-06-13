FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY services/shared/contracts /shared/contracts
COPY services/banking-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt /shared/contracts

COPY services/banking-service/app/ ./app/
COPY services/banking-service/migrations/ ./migrations/
COPY services/banking-service/alembic.ini ./

RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8009

CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8009"]
