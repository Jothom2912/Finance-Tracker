from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

# Taxonomy (categories + subcategories) is owned by categorization-service
# per ADR-003 — the gateway reads it from there, not transaction-service.
CATEGORIZATION_SERVICE_URL = os.getenv("CATEGORIZATION_SERVICE_URL", "http://categorization-service:8005")
CATEGORIZATION_SERVICE_TIMEOUT = float(os.getenv("CATEGORIZATION_SERVICE_TIMEOUT", "5"))

ACCOUNT_SERVICE_URL = os.getenv("ACCOUNT_SERVICE_URL", "http://account-service:8003")
ACCOUNT_SERVICE_TIMEOUT = float(os.getenv("ACCOUNT_SERVICE_TIMEOUT", "5"))

BUDGET_SERVICE_URL = os.getenv("BUDGET_SERVICE_URL", "http://budget-service:8003")
BUDGET_SERVICE_TIMEOUT = float(os.getenv("BUDGET_SERVICE_TIMEOUT", "10"))

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    # Fail fast: an empty secret would make jwt.decode accept tokens
    # signed with "" — refuse to start instead.
    raise RuntimeError(
        "SECRET_KEY environment variable is not set. "
        "The gateway cannot verify JWTs without it — set SECRET_KEY before starting."
    )
JWT_ALGORITHM = "HS256"

CORS_ORIGINS = [
    origin.strip() for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:3001").split(",")
]

ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

SAGA_SERVICE_URL = os.getenv("SAGA_SERVICE_URL", "http://saga-service:8011")
SAGA_SERVICE_TIMEOUT = float(os.getenv("SAGA_SERVICE_TIMEOUT", "5"))

ANALYTICS_SERVICE_URL = os.getenv("ANALYTICS_SERVICE_URL", "http://analytics-service:8000")
ANALYTICS_SERVICE_TIMEOUT = float(os.getenv("ANALYTICS_SERVICE_TIMEOUT", "10"))
