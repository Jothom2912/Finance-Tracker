"""Chat API — asks questions against the user's financial RAG index.

DEPRECATED: Use POST /api/v1/chat/stream for the streaming pipeline.
This endpoint is kept for backward compatibility during frontend migration.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from app.application.chat_service import ChatRequest, ChatResponse, answer_question
from app.auth import get_current_user_id

logger = logging.getLogger(__name__)

chat_router = APIRouter(prefix="/api/v1", tags=["chat"])


@chat_router.post("/chat", response_model=ChatResponse, deprecated=True)
async def chat(
    request: ChatRequest,
    user_id: int = Depends(get_current_user_id),
) -> ChatResponse:
    logger.warning("Deprecated /chat endpoint called — migrate to /chat/stream")
    return await answer_question(request.question, user_id)
