FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY services/budget-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/budget-service/app/ ./app/
COPY services/budget-service/migrations/ ./migrations/
COPY services/budget-service/alembic.ini ./

RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8003

CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8003"]
