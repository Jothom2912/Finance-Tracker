"""Sync categorization endpoint — tier 1 (rule engine), returns instantly.

Called by transaction-service during transaction creation.
Falls back to uncategorized if the pipeline returns only fallback.

The service is built per request (not via Depends) because the user
scope lives in the body: with ``user_id`` set, the engine layers that
user's own rules on top of the global engine (F1-02).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter

from app.application.dto import CategorizeRequestDTO, CategorizeResponseDTO
from app.dependencies import build_categorization_service

logger = logging.getLogger(__name__)

categorize_router = APIRouter(prefix="/api/v1/categorize", tags=["categorization"])


@categorize_router.post(
    "/",
    response_model=CategorizeResponseDTO,
)
async def categorize_single(body: CategorizeRequestDTO) -> CategorizeResponseDTO:
    service = await build_categorization_service(user_id=body.user_id)
    return await service.categorize(body)


@categorize_router.post(
    "/batch",
    response_model=list[CategorizeResponseDTO],
)
async def categorize_batch(body: list[CategorizeRequestDTO]) -> list[CategorizeResponseDTO]:
    # Batches come from single-user flows (CSV import); a mixed batch
    # would be a caller bug — fall back to global rules and say so.
    user_ids = {item.user_id for item in body if item.user_id is not None}
    if len(user_ids) > 1:
        logger.warning("Mixed user_ids in categorize batch — using global rules only")
    user_id = next(iter(user_ids)) if len(user_ids) == 1 else None

    service = await build_categorization_service(user_id=user_id)
    return await service.categorize_batch(body)
