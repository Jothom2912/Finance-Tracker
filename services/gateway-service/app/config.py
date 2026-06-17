from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

TRANSACTION_SERVICE_URL = os.getenv("TRANSACTION_SERVICE_URL", "http://transaction-service:8002")
TRANSACTION_SERVICE_TIMEOUT = float(os.getenv("TRANSACTION_SERVICE_TIMEOUT", "10"))

ACCOUNT_SERVICE_URL = os.getenv("ACCOUNT_SERVICE_URL", "http://account-service:8003")
ACCOUNT_SERVICE_TIMEOUT = float(os.getenv("ACCOUNT_SERVICE_TIMEOUT", "5"))

BUDGET_SERVICE_URL = os.getenv("BUDGET_SERVICE_URL", "http://budget-service:8003")
BUDGET_SERVICE_TIMEOUT = float(os.getenv("BUDGET_SERVICE_TIMEOUT", "10"))

SECRET_KEY = os.getenv("SECRET_KEY", "")
JWT_ALGORITHM = "HS256"

CORS_ORIGINS = [
    origin.strip() for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:3001").split(",")
]

ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

TRANSACTION_PAGE_SIZE = 200

SAGA_SERVICE_URL = os.getenv("SAGA_SERVICE_URL", "http://saga-service:8011")
SAGA_SERVICE_TIMEOUT = float(os.getenv("SAGA_SERVICE_TIMEOUT", "5"))
