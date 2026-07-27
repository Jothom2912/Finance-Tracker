from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///:memory:"
    RABBITMQ_URL: str = "amqp://guest:guest@rabbitmq:5672/"
    ACCOUNT_SERVICE_URL: str = "http://account-service:8003"
    ACCOUNT_SERVICE_TIMEOUT: float = 2.0
    INTERNAL_API_KEY: str | None = None
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:3001"
    ENVIRONMENT: str = "development"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)


settings = Settings()

# Fail fast at startup rather than authenticating with a known dev string
# (P1-15/D1). notification-consumer enriches notifications via account-service;
# with the old default it would have kept calling using a key published in git,
# and after the P2-26 rotation it would have degraded to 401s that read as an
# upstream outage — see app/domain/exceptions.py's note on exactly that.
if not settings.INTERNAL_API_KEY:
    raise ValueError("INTERNAL_API_KEY must be set in environment variables.")
