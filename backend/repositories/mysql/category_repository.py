# backend/repositories/mysql/category_repository.py
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from backend.database.mysql import SessionLocal
from backend.models.mysql.category import Category as CategoryModel
from backend.repositories.base import ICategoryRepository

class MySQLCategoryRepository(ICategoryRepository):
    """MySQL implementation of category repository."""
    
    def __init__(self, db: Session = None):
        self.db = db or SessionLocal()
    
    def get_all(self) -> List[Dict]:
        categories = self.db.query(CategoryModel).all()
        return [self._serialize_category(c) for c in categories]
    
    def get_by_id(self, category_id: int) -> Optional[Dict]:
        category = self.db.query(CategoryModel).filter(
            CategoryModel.idCategory == category_id
        ).first()
        return self._serialize_category(category) if category else None
    
    def get_by_name(self, name: str) -> Optional[Dict]:
        category = self.db.query(CategoryModel).filter(
            CategoryModel.name == name
        ).first()
        return self._serialize_category(category) if category else None
    
    def create(self, category_data: Dict) -> Dict:
        category = CategoryModel(
            name=category_data.get("name"),
            type=category_data.get("type", "expense")
        )
        self.db.add(category)
        self.db.commit()
        self.db.refresh(category)
        return self._serialize_category(category)
    
    def update(self, category_id: int, category_data: Dict) -> Dict:
        category = self.db.query(CategoryModel).filter(
            CategoryModel.idCategory == category_id
        ).first()
        if not category:
            raise ValueError(f"Category {category_id} not found")
        
        if "name" in category_data:
            category.name = category_data["name"]
        if "type" in category_data:
            category.type = category_data["type"]
        
        self.db.commit()
        self.db.refresh(category)
        return self._serialize_category(category)
    
    def delete(self, category_id: int) -> bool:
        category = self.db.query(CategoryModel).filter(
            CategoryModel.idCategory == category_id
        ).first()
        if not category:
            return False
        self.db.delete(category)
        self.db.commit()
        return True
    
    @staticmethod
    def _serialize_category(category: CategoryModel) -> Dict:
        return {
            "idCategory": category.idCategory,
            "name": category.name,
            "type": category.type
        }

