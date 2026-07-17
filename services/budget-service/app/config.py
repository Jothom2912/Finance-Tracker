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
    CATEGORY_SERVICE_URL: str = "http://localhost:8005"
    TRANSACTION_SERVICE_URL: str = "http://localhost:8002"
    REDIS_URL: str = "redis://redis:6379"
    # F1-07 scheduled month-close (worker-loop scheduler)
    MONTH_CLOSE_INTERVAL_SECONDS: int = 3600
    MONTH_CLOSE_DAY: int = 7


settings = Settings()
