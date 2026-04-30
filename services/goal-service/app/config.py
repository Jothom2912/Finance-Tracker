from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///:memory:"
    USER_SERVICE_URL: str = "http://user-service:8001"
    USER_SERVICE_TIMEOUT: float = 2.0
    RABBITMQ_URL: str = "amqp://guest:guest@rabbitmq:5672/"
    INTERNAL_API_KEY: str = "dev-internal-api-key-change-in-production"
    JWT_SECRET: str
    ENVIRONMENT: str = "development"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)


settings = Settings()
