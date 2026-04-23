from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    DATABASE_URL: str
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:3001"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    INTERNAL_API_KEY: str = "dev-internal-api-key-change-in-production"


settings = Settings()
