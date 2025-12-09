from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List, Optional

from backend.models.mysql.category import Category as CategoryModel
# Fjernet importen af TransactionModel her for at undgå cirkulær import ved indlæsning.
from backend.shared.schemas.category import CategoryCreate

# --- CRUD Funktioner ---

def get_category_by_id(db: Session, category_id: int) -> Optional[CategoryModel]:
    """Henter en kategori baseret på ID."""
    return db.query(CategoryModel).filter(CategoryModel.idCategory == category_id).first()

def get_category_by_name(db: Session, name: str) -> Optional[CategoryModel]:
    """Henter en kategori baseret på navn."""
    return db.query(CategoryModel).filter(CategoryModel.name == name).first()

def get_categories(db: Session, skip: int = 0, limit: int = 100) -> List[CategoryModel]:
    """Henter en pagineret liste over kategorier."""
    return db.query(CategoryModel).offset(skip).limit(limit).all()

def create_category(db: Session, category: CategoryCreate) -> CategoryModel:
    """Opretter en ny kategori."""
    if get_category_by_name(db, category.name):
        raise ValueError("Kategori med dette navn eksisterer allerede.")
    
    db_category = CategoryModel(name=category.name, type=category.type)
    
    try:
        db.add(db_category)
        db.commit()
        db.refresh(db_category)
        return db_category
    except IntegrityError:
        db.rollback()
        raise ValueError("Integritetsfejl ved oprettelse af kategori.")

def update_category(db: Session, category_id: int, category_data: CategoryCreate) -> Optional[CategoryModel]:
    """Opdaterer en eksisterende kategori."""
    db_category = get_category_by_id(db, category_id)
    if not db_category:
        return None
    
    # Tjek for duplikat navn, hvis navnet ændres
    if category_data.name != db_category.name and get_category_by_name(db, category_data.name):
        raise ValueError("En anden kategori med dette navn eksisterer allerede.")
        
    db_category.name = category_data.name
    db_category.type = category_data.type
    
    try:
        db.commit()
        db.refresh(db_category)
        return db_category
    except IntegrityError:
        db.rollback()
        raise ValueError("Integritetsfejl ved opdatering af kategori.")

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