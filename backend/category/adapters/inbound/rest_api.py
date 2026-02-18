"""
REST API adapter for Category bounded context.
Handles HTTP concerns and delegates to application service.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from backend.dependencies import get_category_service

from ...application.dto import CategoryCreateDTO, CategoryResponseDTO
from ...application.service import CategoryService
from ...domain.exceptions import DuplicateCategoryName, DuplicateCategoryNameOnUpdate

router = APIRouter(
    prefix="/categories",
    tags=["Categories"],
)


@router.post("/", response_model=CategoryResponseDTO, status_code=status.HTTP_201_CREATED)
def create_category_route(
    category: CategoryCreateDTO,
    service: CategoryService = Depends(get_category_service),
):
    """Opretter en ny kategori."""
    try:
        return service.create_category(category)
    except DuplicateCategoryName as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/", response_model=List[CategoryResponseDTO])
def read_categories_route(
    skip: int = 0,
    limit: int = 100,
    service: CategoryService = Depends(get_category_service),
):
    """Henter alle kategorier."""
    return service.list_categories(skip=skip, limit=limit)


@router.get("/{category_id}", response_model=CategoryResponseDTO)
def read_category_route(
    category_id: int,
    service: CategoryService = Depends(get_category_service),
):
    """Henter kategori by ID."""
    category = service.get_category(category_id)
    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Kategori ikke fundet."
        )
    return category


@router.put("/{category_id}", response_model=CategoryResponseDTO)
def update_category_route(
    category_id: int,
    category: CategoryCreateDTO,
    service: CategoryService = Depends(get_category_service),
):
    """Opdaterer kategori."""
    try:
        updated = service.update_category(category_id, category)
        if updated is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Kategori ikke fundet."
            )
        return updated
    except (DuplicateCategoryName, DuplicateCategoryNameOnUpdate) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category_route(
    category_id: int,
    service: CategoryService = Depends(get_category_service),
):
    """Sletter kategori."""
    if not service.delete_category(category_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Kategori ikke fundet."
        )
    return None
