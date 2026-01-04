# backend/repositories/mysql/category_repository.py
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from backend.models.mysql.category import Category as CategoryModel
from backend.repositories.base import ICategoryRepository

class MySQLCategoryRepository(ICategoryRepository):
    """MySQL implementation of category repository."""
    
    def __init__(self, db: Session):
        """Initialize repository with database session.
        
        Args:
            db: Database session (required - must be provided via Depends(get_db))
        """
        if db is None:
            raise ValueError("db: Session parameter is required")
        self.db = db
    
    def get_all(self, filters: Optional[Dict] = None) -> List[Dict]:
        """Hent alle categories med optional filters
        
        Note: Category model har ikke Account_idAccount, så account_id filter ignoreres.
        """
        try:
            query = self.db.query(CategoryModel)
            
            # Note: Category model har ikke Account_idAccount felt
            # Hvis filters er nødvendigt i fremtiden, skal Category model opdateres først
            
            categories = query.all()
            self.db.commit()  # ✅ Commit efter read
            return [self._serialize_category(c) for c in categories]
        except Exception as e:
            self.db.rollback()  # ✅ Rollback på fejl
            raise ValueError(f"Fejl ved hentning af kategorier: {e}")
    
    def get_by_id(self, category_id: int) -> Optional[Dict]:
        try:
            category = self.db.query(CategoryModel).filter(
                CategoryModel.idCategory == category_id
            ).first()
            self.db.commit()  # ✅ Commit efter read
            return self._serialize_category(category) if category else None
        except Exception as e:
            self.db.rollback()  # ✅ Rollback på fejl
            raise ValueError(f"Fejl ved hentning af kategori: {e}")
    
    def create(self, category_data: Dict) -> Dict:
        try:
            category = CategoryModel(
                name=category_data.get("name"),
                type=category_data.get("type", "expense")
            )
            self.db.add(category)
            self.db.commit()  # ✅ Commit efter write
            self.db.refresh(category)
            return self._serialize_category(category)
        except Exception as e:
            self.db.rollback()  # ✅ Rollback på fejl
            raise ValueError(f"Fejl ved oprettelse af kategori: {e}")
    
    def update(self, category_id: int, category_data: Dict) -> Dict:
        try:
            category = self.db.query(CategoryModel).filter(
                CategoryModel.idCategory == category_id
            ).first()
            if not category:
                self.db.rollback()  # ✅ Rollback når objekt ikke findes
                raise ValueError(f"Category {category_id} not found")
            
            if "name" in category_data:
                category.name = category_data["name"]
            if "type" in category_data:
                category.type = category_data["type"]
            
            self.db.commit()  # ✅ Commit efter write
            self.db.refresh(category)
            return self._serialize_category(category)
        except ValueError:
            raise
        except Exception as e:
            self.db.rollback()  # ✅ Rollback på fejl
            raise ValueError(f"Fejl ved opdatering af kategori: {e}")
    
    def delete(self, category_id: int) -> bool:
        try:
            category = self.db.query(CategoryModel).filter(
                CategoryModel.idCategory == category_id
            ).first()
            if not category:
                self.db.rollback()  # ✅ Rollback når objekt ikke findes
                return False
            
            self.db.delete(category)
            self.db.commit()  # ✅ Commit efter write
            return True
        except Exception as e:
            self.db.rollback()  # ✅ Rollback på fejl
            raise ValueError(f"Fejl ved sletning af kategori: {e}")
    
    @staticmethod
    def _serialize_category(category: CategoryModel) -> Dict:
        return {
            "idCategory": category.idCategory,
            "name": category.name,
            "type": category.type
        }

