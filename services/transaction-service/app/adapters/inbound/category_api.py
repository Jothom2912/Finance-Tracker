from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.application.dto import (
    CategoryResponseDTO,
    CreateCategoryDTO,
    UpdateCategoryDTO,
)
from app.application.ports.inbound import ICategoryService
from app.auth import get_current_user_id
from app.dependencies import get_category_service

category_router = APIRouter(
    prefix="/api/v1/categories",
    tags=["Categories"],
)


@category_router.post(
    "/",
    response_model=CategoryResponseDTO,
    status_code=status.HTTP_201_CREATED,
)
async def create_category(
    body: CreateCategoryDTO,
    _user_id: int = Depends(get_current_user_id),
    service: ICategoryService = Depends(get_category_service),
) -> CategoryResponseDTO:
    return await service.create_category(body)


@category_router.get("/", response_model=list[CategoryResponseDTO])
async def list_categories(
    _user_id: int = Depends(get_current_user_id),
    service: ICategoryService = Depends(get_category_service),
) -> list[CategoryResponseDTO]:
    return await service.get_categories()


@category_router.get("/{category_id}", response_model=CategoryResponseDTO)
async def get_category(
    category_id: int,
    _user_id: int = Depends(get_current_user_id),
    service: ICategoryService = Depends(get_category_service),
) -> CategoryResponseDTO:
    return await service.get_category(category_id)


@category_router.put("/{category_id}", response_model=CategoryResponseDTO)
async def update_category(
    category_id: int,
    body: UpdateCategoryDTO,
    _user_id: int = Depends(get_current_user_id),
    service: ICategoryService = Depends(get_category_service),
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
    service: ICategoryService = Depends(get_category_service),
) -> None:
    await service.delete_category(category_id)
