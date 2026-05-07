"""Chat API — asks questions against the user's financial RAG index."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.application.chat_service import ChatRequest, ChatResponse, answer_question
from app.auth import get_current_user_id

chat_router = APIRouter(prefix="/api/v1", tags=["chat"])


@chat_router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    user_id: int = Depends(get_current_user_id),
) -> ChatResponse:
    return await answer_question(request.question, user_id)
