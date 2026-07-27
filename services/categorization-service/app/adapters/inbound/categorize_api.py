"""Sync categorization endpoint — tier 1 (rule engine), returns instantly.

Called by transaction-service during transaction creation.
Falls back to uncategorized if the pipeline returns only fallback.

The service is built per request (not via Depends) because the user
scope lives in the body: with ``user_id`` set, the engine layers that
user's own rules on top of the global engine (F1-02).
"""

from __future__ import annotations

import logging
from hmac import compare_digest

from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.application.dto import CategorizeRequestDTO, CategorizeResponseDTO
from app.config import settings
from app.dependencies import build_categorization_service

logger = logging.getLogger(__name__)


def require_internal_api_key(
    x_internal_api_key: str | None = Header(default=None, alias="X-Internal-API-Key"),
) -> None:
    """S2S guard — same shape as user-service's internal lookup.

    ``compare_digest`` rather than ``!=`` so a wrong key costs the same
    time regardless of how many leading bytes matched.
    """
    if not settings.INTERNAL_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Sync categorization is not configured",
        )
    if not x_internal_api_key or not compare_digest(x_internal_api_key, settings.INTERNAL_API_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal API key",
        )


# Router-level, not per-endpoint: a future endpoint added to this router
# is then guarded by default rather than by remembering to opt in.
categorize_router = APIRouter(
    prefix="/api/v1/categorize",
    tags=["categorization"],
    dependencies=[Depends(require_internal_api_key)],
)


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
