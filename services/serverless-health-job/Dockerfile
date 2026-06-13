FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir pika==1.3.2 requests==2.32.3

COPY services/serverless-health-job/app ./app

CMD ["python", "-m", "app.main", "run"]
