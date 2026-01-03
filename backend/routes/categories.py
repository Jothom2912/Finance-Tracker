from fastapi import APIRouter, HTTPException, status
from typing import List
from backend.shared.schemas.category import Category as CategorySchema, CategoryCreate
from backend.services import category_service

router = APIRouter(
    prefix="/categories",
    tags=["Categories"]
)

@router.post("/", response_model=CategorySchema, status_code=status.HTTP_201_CREATED)
def create_category_route(category: CategoryCreate):
    """Opretter en ny kategori."""
    try:
        return category_service.create_category(category)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/", response_model=List[CategorySchema])
def read_categories_route(skip: int = 0, limit: int = 100):
    """Henter alle kategorier."""
    return category_service.get_categories(skip=skip, limit=limit)

@router.get("/{category_id}", response_model=CategorySchema)
def read_category_route(category_id: int):
    """Henter kategori by ID."""
    category = category_service.get_category_by_id(category_id)
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kategori ikke fundet.")
    return category

@router.put("/{category_id}", response_model=CategorySchema)
def update_category_route(category_id: int, category: CategoryCreate):
    """Opdaterer kategori."""
    try:
        updated = category_service.update_category(category_id, category)
        if updated is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kategori ikke fundet.")
        return updated
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category_route(category_id: int):
    """Sletter kategori."""
    if not category_service.delete_category(category_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kategori ikke fundet.")
    return None
