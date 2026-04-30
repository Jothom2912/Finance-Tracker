"""Category CRUD endpoints — master taxonomy management.

Categorization-service is the source of truth for categories
and subcategories.  Changes emit category.* events via outbox.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.application.category_service import CategoryService
from app.application.dto import (
    CategoryResponseDTO,
    CreateCategoryDTO,
    SubCategoryResponseDTO,
    UpdateCategoryDTO,
)
from app.auth import get_current_user_id
from app.dependencies import get_category_service

category_router = APIRouter(prefix="/api/v1/categories", tags=["categories"])


@category_router.post(
    "/",
    response_model=CategoryResponseDTO,
    status_code=status.HTTP_201_CREATED,
)
async def create_category(
    body: CreateCategoryDTO,
    _user_id: int = Depends(get_current_user_id),
    service: CategoryService = Depends(get_category_service),
) -> CategoryResponseDTO:
    return await service.create_category(body)


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


@category_router.put("/{category_id}", response_model=CategoryResponseDTO)
async def update_category(
    category_id: int,
    body: UpdateCategoryDTO,
    _user_id: int = Depends(get_current_user_id),
    service: CategoryService = Depends(get_category_service),
) -> CategoryResponseDTO:
    return await service.update_category(category_id, body)


@category_router.delete(
    "/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def delete_category(
    category_id: int,
    _user_id: int = Depends(get_current_user_id),
    service: CategoryService = Depends(get_category_service),
) -> None:
    await service.delete_category(category_id)


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
