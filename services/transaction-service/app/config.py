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
    CATEGORIZATION_SERVICE_URL: str = "http://localhost:8005"
    CATEGORIZATION_TIMEOUT_S: float = 0.5
    INTERNAL_API_KEY: str | None = None

    # CSV-import guards (P2-29). Both are enforced; they catch different files.
    # CSV_MAX_BYTES bounds peak memory: import_csv holds three live copies of
    # the payload (bytes → str → StringIO), and the k8s pod is capped at 512Mi,
    # so 10 MiB peaks at ~30 MiB (~6%). CSV_MAX_ROWS bounds the single
    # bulk_create + outbox batch; at ~76 bytes/row a realistic 5-year bank
    # export is ~3 000 rows, so this is ~17x headroom and is the limit that
    # actually binds for well-formed files.
    CSV_MAX_BYTES: int = 10 * 1024 * 1024
    CSV_MAX_ROWS: int = 50_000


settings = Settings()
