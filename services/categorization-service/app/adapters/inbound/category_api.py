"""Category read endpoints.

Per ADR-002, transaction-service is the authoritative writer for the
categories table; categorization-service keeps a read-copy in sync via
``CategorySyncConsumer``.  The write endpoints (POST/PUT/DELETE) were
therefore removed from this router to close the split-brain — see Fase 1
of the category-consistency work.  Only read routes remain, because
budget-service depends on them (``CategoryPort`` reads category names and
existence from cat-service; see NOTE in ADR-002 about the dual read source).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.application.category_service import CategoryService
from app.application.dto import (
    CategoryResponseDTO,
    SubCategoryResponseDTO,
)
from app.auth import get_current_user_id
from app.dependencies import get_category_service

category_router = APIRouter(prefix="/api/v1/categories", tags=["categories"])


@category_router.get("/", response_model=list[CategoryResponseDTO])
async def list_categories(
    _user_id: int = Depends(get_current_user_id),
    service: CategoryService = Depends(get_category_service),
) -> list[CategoryResponseDTO]:
    return await service.list_categories()


@category_router.get("/{category_id}", response_model=CategoryResponseDTO)
async def get_category(
    category_id: int,
    _user_id: int = Depends(get_current_user_id),
    service: CategoryService = Depends(get_category_service),
) -> CategoryResponseDTO:
    return await service.get_category(category_id)


@category_router.get(
    "/{category_id}/subcategories",
    response_model=list[SubCategoryResponseDTO],
)
async def list_subcategories(
    category_id: int,
    _user_id: int = Depends(get_current_user_id),
    service: CategoryService = Depends(get_category_service),
) -> list[SubCategoryResponseDTO]:
    return await service.list_subcategories(category_id)
