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

    ACCOUNT_SERVICE_URL: str = "http://account-service:8003"
    ACCOUNT_SERVICE_TIMEOUT: float = 2.0
    INTERNAL_API_KEY: str = "dev-internal-api-key-change-in-production"

    ENABLE_BANKING_APP_ID: str = ""
    ENABLE_BANKING_KEY_PATH: str = ""
    ENABLE_BANKING_REDIRECT_URI: str = ""
    # Cap on continuation-key pagination per transaction fetch; a hit
    # logs a WARNING and truncates rather than looping unbounded.
    MAX_TX_PAGES: int = 20

    FRONTEND_URL: str = "http://localhost:3000"

    PENDING_AUTH_TTL_MINUTES: int = 15

    # P3-14 sync-claim: status-opslag ved claim-konflikt + TTL-backstop
    # (600s = 2x saga-timeout-workerens 300s idle-graense).
    SAGA_SERVICE_URL: str = "http://saga-service:8011"
    SAGA_SERVICE_TIMEOUT: float = 2.0
    SYNC_CLAIM_TTL_SECONDS: int = 600

    # F1-05 scheduled bank sync (worker-loop scheduler): sync naar sidste
    # sync er aeldre end SYNC_EVERY_HOURS, tjekket hvert tick.
    SYNC_SCHEDULER_INTERVAL_SECONDS: int = 3600
    SYNC_EVERY_HOURS: int = 24
    SYNC_CONSENT_WARN_DAYS: int = 7


settings = Settings()
