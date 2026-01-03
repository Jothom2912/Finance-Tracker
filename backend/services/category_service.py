from backend.repositories import get_category_repository
from typing import List, Optional

from backend.shared.schemas.category import CategoryCreate

# --- CRUD Funktioner ---

def get_category_by_id(category_id: int) -> Optional[dict]:
    """Henter en kategori baseret på ID."""
    repo = get_category_repository()
    return repo.get_by_id(category_id)

def get_category_by_name(name: str) -> Optional[dict]:
    """Henter en kategori baseret på navn."""
    repo = get_category_repository()
    return repo.get_by_name(name)

def get_categories(skip: int = 0, limit: int = 100) -> List[dict]:
    """Henter en pagineret liste over kategorier."""
    repo = get_category_repository()
    return repo.get_all(skip=skip, limit=limit)

def create_category(category: CategoryCreate) -> dict:
    """Opretter en ny kategori."""
    repo = get_category_repository()
    if repo.get_by_name(category.name):
        raise ValueError("Kategori med dette navn eksisterer allerede.")
    
    category_data = category.model_dump()
    return repo.create(category_data)

def update_category(category_id: int, category_data: CategoryCreate) -> Optional[dict]:
    """Opdaterer en eksisterende kategori."""
    repo = get_category_repository()
    existing_category = repo.get_by_id(category_id)
    if not existing_category:
        return None
    
    # Tjek for duplikat navn, hvis navnet ændres
    if category_data.name != existing_category["name"] and get_category_by_name(category_data.name):
        raise ValueError("En anden kategori med dette navn eksisterer allerede.")
    
    update_data = category_data.model_dump()
    return repo.update(category_id, update_data)

def delete_category(category_id: int) -> bool:
    """Sletter en kategori."""
    repo = get_category_repository()
    return repo.delete(category_id)