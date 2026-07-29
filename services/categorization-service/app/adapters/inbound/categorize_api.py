"""Sync categorization endpoint — tier 1 (rule engine), returns instantly.

Called by transaction-service during transaction creation, and by nothing
else: this router is S2S-only (P1-15).
Falls back to uncategorized if the pipeline returns only fallback.

The sync path runs **global rules only**. Per-user rule layering (F1-02)
lives on the async consumer path, which takes ``user_id`` from the event.
That is not a change in behavior: transaction-service has never sent a
``user_id`` on this path, so the body field only ever let an unauthenticated
caller probe another user's private rules through the ``tier`` field.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends

from app.adapters.inbound.internal_auth import require_internal_api_key
from app.application.dto import CategorizeRequestDTO, CategorizeResponseDTO
from app.config import settings
from app.dependencies import build_categorization_service

# Same ceiling as transaction-service's BulkCreateTransactionDTO, which is
# the only producer of batches — an unbounded list would be a cheap way to
# tie up the rule engine.
MAX_BATCH_ITEMS = 500

# Re-exported for the tests that monkeypatch this module's ``settings``.
__all__ = ["MAX_BATCH_ITEMS", "categorize_router", "require_internal_api_key", "settings"]


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
    service = await build_categorization_service(user_id=None)
    return await service.categorize(body)


@categorize_router.post(
    "/batch",
    response_model=list[CategorizeResponseDTO],
)
async def categorize_batch(
    body: Annotated[
        list[CategorizeRequestDTO],
        Body(min_length=1, max_length=MAX_BATCH_ITEMS),
    ],
) -> list[CategorizeResponseDTO]:
    service = await build_categorization_service(user_id=None)
    return await service.categorize_batch(body)
