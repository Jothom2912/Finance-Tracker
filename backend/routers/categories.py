from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
from typing import List, Optional

# --- VIGTIGE ÆNDRINGER HER ---
# Importer dine Pydantic-skemaer, alias 'Category' som 'CategorySchema'
from backend.schemas.category import Category as CategorySchema, CategoryCreate, CategoryBase
# Importér dine SQLAlchemy-modeller direkte fra database.py
from backend.database import get_db, Category, Transaction # <-- Category her er din SQLAlchemy ORM model!

router = APIRouter(
    prefix="/categories",
    tags=["Categories"]
)

# --- Endpoint for at oprette en ny kategori ---
@router.post("/", response_model=CategorySchema) # Brug CategorySchema her
def create_category(category: CategoryCreate, db: Session = Depends(get_db)):
    """
    Opretter en ny kategori manuelt.
    """
    try:
        # Brug den importerede SQLAlchemy Category-model her
        db_category_exists = db.query(Category).filter(Category.name == category.name).first()
        if db_category_exists:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Kategori med dette navn eksisterer allerede."
            )

        # Brug den importerede SQLAlchemy Category-model her
        db_category = Category(name=category.name, type=category.type)
        db.add(db_category)
        db.commit()
        db.refresh(db_category)
        return db_category
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Kategori med dette navn eksisterer allerede (databasekonflikt)."
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Der opstod en uventet fejl ved oprettelse af kategori: {e}"
        )


# --- Endpoint for at hente alle kategorier ---
@router.get("/", response_model=List[CategorySchema]) # Brug CategorySchema her
def read_categories(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    Henter en liste over alle kategorier.
    """
    # Brug den importerede SQLAlchemy Category-model her
    categories = db.query(Category).offset(skip).limit(limit).all()
    return categories

# --- Endpoint for at hente en specifik kategori ud fra ID ---
@router.get("/{category_id}", response_model=CategorySchema) # Brug CategorySchema her
def read_category(category_id: int, db: Session = Depends(get_db)):
    """
    Henter detaljer for en specifik kategori baseret på ID.
    """
    # Brug den importerede SQLAlchemy Category-model her
    category = db.query(Category).filter(Category.id == category_id).first()
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kategori ikke fundet.")
    return category

# --- Endpoint for at opdatere en kategori ---
@router.put("/{category_id}", response_model=CategorySchema) # Brug CategorySchema her
def update_category(category_id: int, category: CategoryCreate, db: Session = Depends(get_db)):
    """
    Opdaterer en eksisterende kategori baseret på ID.
    """
    # Brug den importerede SQLAlchemy Category-model her
    db_category = db.query(Category).filter(Category.id == category_id).first()
    if db_category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kategori ikke fundet.")

    # Tjek for duplikat navn, hvis navnet ændres til et eksisterende
    if category.name != db_category.name:
        try:
            # Brug den importerede SQLAlchemy Category-model her
            existing_category = db.query(Category).filter(Category.name == category.name).first()
            if existing_category:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="En anden kategori med dette navn eksisterer allerede."
                )

            db_category.name = category.name
            db_category.type = category.type
            db.commit()
            db.refresh(db_category)
            return db_category

        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Kategori med dette navn eksisterer allerede (databasekonflikt ved opdatering)."
            )
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Der opstod en uventet fejl ved opdatering af kategori: {e}"
            )
    else:
        db_category.type = category.type
        db.commit()
        db.refresh(db_category)
        return db_category


# --- Endpoint for at slette en kategori ---
@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(category_id: int, db: Session = Depends(get_db)):
    """
    Sletter en kategori baseret på ID.
    """
    # Brug den importerede SQLAlchemy Category-model her
    db_category = db.query(Category).filter(Category.id == category_id).first()
    if db_category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kategori ikke fundet.")

    try:
        # Brug den importerede SQLAlchemy Transaction-model her
        db.query(Transaction).filter(Transaction.category_id == category_id).update({"category_id": None})

        db.delete(db_category)
        db.commit()
        return None
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Fejl ved sletning af kategori eller opdatering af relaterede transaktioner: {e}"
        )