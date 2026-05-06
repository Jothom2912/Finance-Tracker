"""Ingest API — triggers embedding of user transactions into ChromaDB."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.application.ingest_service import ingest_transactions
from app.auth import get_current_user_id

ingest_router = APIRouter(prefix="/api/v1", tags=["ingest"])


def _extract_token(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    return auth.removeprefix("Bearer ").strip()


@ingest_router.post("/ingest")
async def ingest(
    request: Request,
    user_id: int = Depends(get_current_user_id),
) -> dict:
    token = _extract_token(request)
    count = await ingest_transactions(user_id, token)
    return {"status": "ok", "transactions_ingested": count}
