from typing import List, Optional, Dict
from sqlalchemy.orm import Session
from backend.repositories import get_category_repository
from backend.shared.schemas.category import CategoryCreate

def get_category_by_id(category_id: int, db: Session) -> Optional[Dict]:
    """Henter en kategori baseret på ID."""
    repo = get_category_repository(db)
    return repo.get_by_id(category_id)

def get_category_by_name(name: str, db: Session) -> Optional[Dict]:
    """Henter en kategori baseret på navn."""
    repo = get_category_repository(db)
    categories = repo.get_all()
    for cat in categories:
        if cat.get("name") == name:
            return cat
    return None

def get_categories(skip: int = 0, limit: int = 100, db: Session = None) -> List[Dict]:
    """Henter en pagineret liste over kategorier."""
    if db is None:
        raise ValueError("db: Session parameter is required")
    repo = get_category_repository(db)
    all_categories = repo.get_all()
    return all_categories[skip:skip + limit]

def create_category(category: CategoryCreate, db: Session) -> Dict:
    """Opretter en ny kategori."""
    if get_category_by_name(category.name, db):
        raise ValueError("Kategori med dette navn eksisterer allerede.")
    
    repo = get_category_repository(db)
    category_data = {
        "name": category.name,
        "type": category.type.value if hasattr(category.type, 'value') else category.type
    }
    return repo.create(category_data)

def update_category(category_id: int, category_data: CategoryCreate, db: Session) -> Optional[Dict]:
    """Opdaterer en eksisterende kategori."""
    repo = get_category_repository(db)
    
    existing = repo.get_by_id(category_id)
    if not existing:
        return None
    
    # Tjek for duplikat navn
    if category_data.name != existing.get("name"):
        if get_category_by_name(category_data.name, db):
            raise ValueError("En anden kategori med dette navn eksisterer allerede.")
    
    update_data = {
        "name": category_data.name,
        "type": category_data.type.value if hasattr(category_data.type, 'value') else category_data.type
    }
    return repo.update(category_id, update_data)

def delete_category(category_id: int, db: Session) -> bool:
    """Sletter en kategori."""
    repo = get_category_repository(db)
    return repo.delete(category_id)
