from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///:memory:"
    RABBITMQ_URL: str = "amqp://guest:guest@rabbitmq:5672/"
    ACCOUNT_SERVICE_URL: str = "http://account-service:8003"
    ACCOUNT_SERVICE_TIMEOUT: float = 2.0
    INTERNAL_API_KEY: str = "dev-internal-api-key-change-in-production"
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:3001"
    ENVIRONMENT: str = "development"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)


settings = Settings()
