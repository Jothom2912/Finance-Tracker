FROM python:3.11-slim

WORKDIR /app

COPY services/account-service/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY services/account-service/app ./app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8003"]