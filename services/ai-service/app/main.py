from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.adapters.inbound.chat_api import chat_router
from app.adapters.inbound.ingest_api import ingest_router
from app.config import settings

logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI Service",
    version="0.1.0",
    description="RAG-based Q&A chat service for personal finance data. "
    "Uses Ollama (local LLM) with ChromaDB vector store.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(ingest_router)
app.include_router(chat_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy", "service": "ai-service"}
