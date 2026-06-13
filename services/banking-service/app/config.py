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

    TRANSACTION_SERVICE_URL: str = "http://transaction-service:8002"
    TRANSACTION_SERVICE_TIMEOUT: float = 10.0
    ACCOUNT_SERVICE_URL: str = "http://account-service:8003"
    ACCOUNT_SERVICE_TIMEOUT: float = 2.0
    INTERNAL_API_KEY: str = "dev-internal-api-key-change-in-production"

    ENABLE_BANKING_APP_ID: str = ""
    ENABLE_BANKING_KEY_PATH: str = ""
    ENABLE_BANKING_REDIRECT_URI: str = ""

    FRONTEND_URL: str = "http://localhost:3000"

    PENDING_AUTH_TTL_MINUTES: int = 15


settings = Settings()
