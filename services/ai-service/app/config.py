from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    OLLAMA_BASE_URL: str = "http://ollama:11434"
    LLM_ROUTER_MODEL: str = "qwen3:4b"
    LLM_RESPONDER_MODEL: str = "qwen3:8b"
    LLM_ROUTER_KEEP_ALIVE: int = -1
    LLM_RESPONDER_KEEP_ALIVE: int = -1
    EMBEDDING_MODEL: str = "bge-m3"
    TRANSACTION_SERVICE_URL: str = "http://transaction-service:8002"
    ANALYTICS_SERVICE_URL: str = "http://analytics-service:8000"
    BUDGET_SERVICE_URL: str = "http://budget-service:8003"
    CHROMADB_PATH: str = "/data/chromadb"
    RETRIEVAL_TOP_K: int = 10
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:3001"


settings = Settings()
