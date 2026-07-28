from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///:memory:"
    USER_SERVICE_URL: str = "http://user-service:8001"
    USER_SERVICE_TIMEOUT: float = 2.0
    ACCOUNT_SERVICE_URL: str = "http://account-service:8003"
    ACCOUNT_SERVICE_TIMEOUT: float = 2.0
    RABBITMQ_URL: str = "amqp://guest:guest@rabbitmq:5672/"
    INTERNAL_API_KEY: str | None = None
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ENVIRONMENT: str = "development"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)


settings = Settings()

# Fail fast at startup rather than authenticating with a known dev string
# (P1-15/D1). Defaulting INTERNAL_API_KEY to "dev-internal-api-key-…" meant a
# container that never got the variable still made *authenticated-looking*
# internal calls with a key everyone could read from git — and after the P2-26
# rotation it silently sent the wrong key instead. Crash-looping here is the
# intended outcome: it names the missing variable instead of hiding it.
if not settings.INTERNAL_API_KEY:
    raise ValueError("INTERNAL_API_KEY must be set in environment variables.")
