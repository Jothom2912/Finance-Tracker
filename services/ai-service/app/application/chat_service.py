"""Chat service — orchestrates retrieval, prompt building, and LLM generation."""

from __future__ import annotations

import logging
from typing import Any

import anyio
from pydantic import BaseModel, Field

from app.adapters.outbound.llm_client import generate_answer
from app.application.retriever import retrieve
from app.prompts.finance_qa import build_finance_qa_prompt

logger = logging.getLogger(__name__)


class ChatSource(BaseModel):
    transaction_id: int | None = None
    date: str | None = None
    amount: float | None = None
    category: str | None = None
    description: str | None = None
    document: str
    distance: float


class ChatResponse(BaseModel):
    answer: str
    sources: list[ChatSource]
    source_count: int


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


async def answer_question(question: str, user_id: int) -> ChatResponse:
    """Answer a user's question using retrieved transaction context."""
    retrieved = await anyio.to_thread.run_sync(retrieve, question, user_id)
    sources = [_to_source(item) for item in retrieved]

    if not retrieved:
        return ChatResponse(
            answer=(
                "Jeg fandt ingen relevante transaktioner i vidensbasen. "
                "Proev at opdatere vidensbasen eller stille spoergsmaalet mere specifikt."
            ),
            sources=[],
            source_count=0,
        )

    prompt = build_finance_qa_prompt(question, retrieved)
    logger.info("RAG prompt for user %d:\n%s", user_id, prompt)

    answer = await anyio.to_thread.run_sync(generate_answer, prompt)
    return ChatResponse(answer=answer, sources=sources, source_count=len(sources))


def _to_source(item: dict[str, Any]) -> ChatSource:
    metadata = item.get("metadata") or {}
    return ChatSource(
        transaction_id=metadata.get("transaction_id"),
        date=metadata.get("date"),
        amount=metadata.get("amount"),
        category=metadata.get("category"),
        description=metadata.get("description"),
        document=item.get("document", ""),
        distance=float(item.get("distance", 0.0)),
    )
