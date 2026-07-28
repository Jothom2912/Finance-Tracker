from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    DATABASE_URL: str
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    ACCOUNT_SERVICE_URL: str = "http://account-service:8003"
    ACCOUNT_SERVICE_TIMEOUT: float = 2.0
    INTERNAL_API_KEY: str | None = None

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

# Fail fast at startup rather than authenticating with a known dev string
# (P1-15/D1). banking-sync-scheduler was the concrete case: its compose block
# never set INTERNAL_API_KEY, so it called account-service with the committed
# dev default — and after the P2-26 rotation it sent a key account-service no
# longer accepts. The bug was invisible because the scheduler only reaches
# account-service once a real bank connection exists.
if not settings.INTERNAL_API_KEY:
    raise ValueError("INTERNAL_API_KEY must be set in environment variables.")
