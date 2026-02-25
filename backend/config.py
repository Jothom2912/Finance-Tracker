# backend/config.py
"""
Centralized configuration - all environment variables are loaded here.
Other modules should import config values from this module instead of
calling os.getenv() or load_dotenv() directly.
"""
import os
from enum import Enum
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root (parent of backend/)
_env_path = Path(__file__).parent.parent / ".env"
if not _env_path.exists():
    # Fallback: try backend directory
    _env_path = Path(__file__).parent / ".env"

load_dotenv(dotenv_path=_env_path)


# =============================================================================
# Database Configuration
# =============================================================================

class DatabaseType(Enum):
    MYSQL = "mysql"
    ELASTICSEARCH = "elasticsearch"
    NEO4J = "neo4j"
    HYBRID = "hybrid"

ACTIVE_DB = os.getenv("ACTIVE_DB", DatabaseType.MYSQL.value)
DATABASE_URL = os.getenv("DATABASE_URL")

# Domain-level DB roles (prepares split into microservices).
# Defaults keep current behavior if only ACTIVE_DB is configured.
TRANSACTIONS_DB = os.getenv("TRANSACTIONS_DB", DatabaseType.MYSQL.value)
ANALYTICS_DB = os.getenv("ANALYTICS_DB", ACTIVE_DB)
USER_DB = os.getenv("USER_DB", DatabaseType.MYSQL.value)

ELASTICSEARCH_HOST = os.getenv("ELASTICSEARCH_HOST", "http://localhost:9200")
SYNC_TO_ELASTICSEARCH = os.getenv("SYNC_TO_ELASTICSEARCH", "false").lower() == "true"

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
USE_NEO4J = os.getenv("USE_NEO4J", "false").lower() == "true"


# =============================================================================
# Security Configuration
# =============================================================================

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))


# =============================================================================
# Application / Observability
# =============================================================================

ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()


# =============================================================================
# CORS Configuration
# =============================================================================

CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:3001").split(",")
]
