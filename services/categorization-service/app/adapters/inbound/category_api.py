"""Taxonomy endpoints — categories and subcategories.

Per ADR-003 (supersedes ADR-002), categorization-service is the sole
owner and writer of the full taxonomy. Write routes emit full-state
``category.*`` / ``subcategory.*`` events via the transactional outbox;
transaction-service maintains event-synced read copies.

Routing layout:
- ``/api/v1/categories``: category CRUD + nested subcategory list/create
- ``/api/v1/subcategories``: flat list-all (for gateway, avoids N+1) and
  item-level update/delete
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.application.category_service import CategoryService
from app.application.dto import (
    CategoryResponseDTO,
    CreateCategoryDTO,
    CreateSubCategoryDTO,
    SubCategoryResponseDTO,
    UpdateCategoryDTO,
    UpdateSubCategoryDTO,
)
from app.auth import get_current_user_id
from app.dependencies import get_category_service

category_router = APIRouter(prefix="/api/v1/categories", tags=["categories"])
subcategory_router = APIRouter(prefix="/api/v1/subcategories", tags=["subcategories"])


# ── Categories ──


@category_router.get("/", response_model=list[CategoryResponseDTO])
async def list_categories(
    _user_id: int = Depends(get_current_user_id),
    service: CategoryService = Depends(get_category_service),
) -> list[CategoryResponseDTO]:
    return await service.list_categories()


@category_router.post("/", response_model=CategoryResponseDTO, status_code=status.HTTP_201_CREATED)
async def create_category(
    dto: CreateCategoryDTO,
    _user_id: int = Depends(get_current_user_id),
    service: CategoryService = Depends(get_category_service),
) -> CategoryResponseDTO:
    return await service.create_category(dto)


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
    dto: UpdateCategoryDTO,
    _user_id: int = Depends(get_current_user_id),
    service: CategoryService = Depends(get_category_service),
) -> CategoryResponseDTO:
    return await service.update_category(category_id, dto)


@category_router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: int,
    _user_id: int = Depends(get_current_user_id),
    service: CategoryService = Depends(get_category_service),
) -> None:
    await service.delete_category(category_id)


# ── Subcategories (nested under parent) ──


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


@category_router.post(
    "/{category_id}/subcategories",
    response_model=SubCategoryResponseDTO,
    status_code=status.HTTP_201_CREATED,
)
async def create_subcategory(
    category_id: int,
    dto: CreateSubCategoryDTO,
    _user_id: int = Depends(get_current_user_id),
    service: CategoryService = Depends(get_category_service),
) -> SubCategoryResponseDTO:
    return await service.create_subcategory(category_id, dto)


# ── Subcategories (flat item/list routes) ──


@subcategory_router.get("/", response_model=list[SubCategoryResponseDTO])
async def list_all_subcategories(
    _user_id: int = Depends(get_current_user_id),
    service: CategoryService = Depends(get_category_service),
) -> list[SubCategoryResponseDTO]:
    return await service.list_all_subcategories()


@subcategory_router.put("/{subcategory_id}", response_model=SubCategoryResponseDTO)
async def update_subcategory(
    subcategory_id: int,
    dto: UpdateSubCategoryDTO,
    _user_id: int = Depends(get_current_user_id),
    service: CategoryService = Depends(get_category_service),
) -> SubCategoryResponseDTO:
    return await service.update_subcategory(subcategory_id, dto)


@subcategory_router.delete("/{subcategory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subcategory(
    subcategory_id: int,
    _user_id: int = Depends(get_current_user_id),
    service: CategoryService = Depends(get_category_service),
) -> None:
    await service.delete_subcategory(subcategory_id)
