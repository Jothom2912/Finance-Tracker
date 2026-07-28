from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    DATABASE_URL: str
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    # No dev-string default: an unconfigured key must make /categorize
    # answer 503, not accept a well-known value (P1-15).
    INTERNAL_API_KEY: str | None = None


settings = Settings()
