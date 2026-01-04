from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
from sqlalchemy.orm import Session
from backend.shared.schemas.category import Category as CategorySchema, CategoryCreate
from backend.services import category_service
from backend.database.mysql import get_db

router = APIRouter(
    prefix="/categories",
    tags=["Categories"]
)

@router.post("/", response_model=CategorySchema, status_code=status.HTTP_201_CREATED)
def create_category_route(category: CategoryCreate, db: Session = Depends(get_db)):
    """Opretter en ny kategori."""
    try:
        return category_service.create_category(category, db)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/", response_model=List[CategorySchema])
def read_categories_route(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Henter alle kategorier."""
    return category_service.get_categories(skip=skip, limit=limit, db=db)

@router.get("/{category_id}", response_model=CategorySchema)
def read_category_route(category_id: int, db: Session = Depends(get_db)):
    """Henter kategori by ID."""
    category = category_service.get_category_by_id(category_id, db)
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kategori ikke fundet.")
    return category

@router.put("/{category_id}", response_model=CategorySchema)
def update_category_route(category_id: int, category: CategoryCreate, db: Session = Depends(get_db)):
    """Opdaterer kategori."""
    try:
        updated = category_service.update_category(category_id, category, db)
        if updated is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kategori ikke fundet.")
        return updated
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category_route(category_id: int, db: Session = Depends(get_db)):
    """Sletter kategori."""
    if not category_service.delete_category(category_id, db):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kategori ikke fundet.")
    return None
