from backend.repositories import get_category_repository
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List, Optional

from backend.models.mysql.category import Category as CategoryModel
# Fjernet importen af TransactionModel her for at undgå cirkulær import ved indlæsning.
from backend.shared.schemas.category import CategoryCreate

# --- CRUD Funktioner ---

def get_category_by_id( category_id: int) -> Optional[CategoryModel]:
    """Henter en kategori baseret på ID."""
    repo= get_category_repository()
    return repo.get_by_id(category_id)

def get_category_by_name(name: str) -> Optional[CategoryModel]:
    """Henter en kategori baseret på navn."""
    repo=get_category_repository()
    return repo.get_by_name(name)

def get_categories(skip: int = 0, limit: int = 100) -> List[CategoryModel]:
    """Henter en pagineret liste over kategorier."""
    repo = get_category_repository()
    return repo.get_all(skip=skip, limit=limit)

def create_category( category: CategoryCreate) -> CategoryModel:
    """Opretter en ny kategori."""
    repo=get_category_repository()
    if repo.get_by_name(category.name):
        raise ValueError("Kategori med dette navn eksisterer allerede.")
    
    db_category = CategoryModel(name=category.name, type=category.type)
    
    try:
        repo.create(db_category)
        return db_category
    except IntegrityError:
        raise ValueError("Integritetsfejl ved oprettelse af kategori.")

def update_category( category_id: int, category_data: CategoryCreate) -> Optional[CategoryModel]:
    """Opdaterer en eksisterende kategori."""
    repo=get_category_repository()
    db_category = repo.get_by_id(category_id)
    if not db_category:
        return None
    
    # Tjek for duplikat navn, hvis navnet ændres
    if category_data.name != db_category.name and get_category_by_name(category_data.name):
        raise ValueError("En anden kategori med dette navn eksisterer allerede.")
        
    db_category.name = category_data.name
    db_category.type = category_data.type

def delete_category(db: Session, category_id: int) -> bool:
    """Sletter en kategori og nulstiller relaterede transaktioner."""
    db_category = get_category_by_id(db, category_id)
    if not db_category:
        return False

    # LØSNING PÅ CIRKULÆR IMPORT: Lazy Import af TransactionModel
    from backend.models.mysql.transaction import Transaction as TransactionModel 

    try:
        # Sæt category_id til NULL for alle relaterede transaktioner
        db.query(TransactionModel).filter(TransactionModel.Category_idCategory == category_id).update(
            {"Category_idCategory": None}
        )

        db.delete(db_category)
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        raise Exception(f"Fejl ved sletning af kategori: {e}")