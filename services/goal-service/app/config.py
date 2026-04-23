from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    DATABASE_URL: str
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:3001"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    USER_SERVICE_URL: str = "http://localhost:8001"
    USER_SERVICE_TIMEOUT: float = 5.0
    INTERNAL_API_KEY: str = "dev-internal-api-key-change-in-production"


settings = Settings()
