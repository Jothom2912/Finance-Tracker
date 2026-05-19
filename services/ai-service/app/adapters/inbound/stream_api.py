"""SSE streaming endpoint for the chat pipeline.

POST /api/v1/chat/stream returns an EventSourceResponse where each SSE event
uses the discriminator field as event-name, so frontend can use
addEventListener("intent_resolved", ...) directly.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse, ServerSentEvent

from app.application.pipeline import run_pipeline
from app.auth import get_current_user_id

logger = logging.getLogger(__name__)

stream_router = APIRouter(prefix="/api/v1", tags=["chat-stream"])

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
}


class ChatStreamRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


def _get_account_id(request: Request) -> int:
    raw = request.headers.get("X-Account-ID")
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Account-ID header is required",
        )
    try:
        return int(raw)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Account-ID must be an integer",
        ) from err


def _get_token(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return ""


@stream_router.post("/chat/stream")
async def chat_stream(
    body: ChatStreamRequest,
    request: Request,
    user_id: int = Depends(get_current_user_id),
    account_id: int = Depends(_get_account_id),
) -> EventSourceResponse:
    token = _get_token(request)

    async def event_generator():
        async for event in run_pipeline(
            question=body.question,
            user_id=user_id,
            account_id=account_id,
            token=token,
            request=request,
        ):
            yield ServerSentEvent(
                data=event.data.model_dump_json(),
                event=event.event,
            )

    return EventSourceResponse(
        event_generator(),
        headers=_SSE_HEADERS,
    )
