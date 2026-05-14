from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    OLLAMA_BASE_URL: str = "http://ollama:11434"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    LLM_MODEL: str = "qwen3:1.7b"
    LLM_MODEL: str = "qwen3:4b"
    EMBEDDING_MODEL: str = "embeddinggemma:latest"
    TRANSACTION_SERVICE_URL: str = "http://transaction-service:8002"
    CHROMADB_PATH: str = "/data/chromadb"
    RETRIEVAL_TOP_K: int = 30
    RETRIEVAL_TOP_K: int = 15
    RETRIEVAL_TOP_K: int = 50
    JWT_SECRET: str = ""
    JWT_ALGORITHM: str = "HS256"
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:3001"
    ENVIRONMENT: str = "development"


settings = Settings()
