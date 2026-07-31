from __future__ import annotations

import logging

from fastapi import FastAPI
from observability import setup_logging

from app.adapters.inbound.stream_api import stream_router

# P3-57: uvicorn konfigurerer kun sine egne loggere — uden dette arver app.* root's WARNING.
setup_logging()

logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI Service",
    version="0.1.0",
    description="RAG-based Q&A chat service for personal finance data. "
    "Uses Ollama (local LLM) with Elasticsearch hybrid search via analytics-service.",
)


app.include_router(stream_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy", "service": "ai-service"}
