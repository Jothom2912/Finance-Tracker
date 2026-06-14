from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///:memory:"
    RABBITMQ_URL: str = "amqp://guest:guest@rabbitmq:5672/"
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:3001"
    ENVIRONMENT: str = "development"
    SAGA_TIMEOUT_SECONDS: int = 300
    TIMEOUT_CHECK_INTERVAL_SECONDS: int = 30

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)


settings = Settings()
