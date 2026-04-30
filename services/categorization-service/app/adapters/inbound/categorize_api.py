"""Sync categorization endpoint — tier 1 (rule engine), returns instantly.

Called by transaction-service during transaction creation.
Falls back to uncategorized if the pipeline returns only fallback.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.application.categorization_service import CategorizationService
from app.application.dto import CategorizeRequestDTO, CategorizeResponseDTO
from app.dependencies import get_categorization_service

categorize_router = APIRouter(prefix="/api/v1/categorize", tags=["categorization"])


@categorize_router.post(
    "/",
    response_model=CategorizeResponseDTO,
)
async def categorize_single(
    body: CategorizeRequestDTO,
    service: CategorizationService = Depends(get_categorization_service),
) -> CategorizeResponseDTO:
    return await service.categorize(body)


@categorize_router.post(
    "/batch",
    response_model=list[CategorizeResponseDTO],
)
async def categorize_batch(
    body: list[CategorizeRequestDTO],
    service: CategorizationService = Depends(get_categorization_service),
) -> list[CategorizeResponseDTO]:
    return await service.categorize_batch(body)
