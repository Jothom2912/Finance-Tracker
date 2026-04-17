"""
MySQL adapter for SubCategory repository.
"""

from typing import Optional

from sqlalchemy.orm import Session

from backend.category.application.ports.outbound import ISubCategoryRepository
from backend.category.domain.entities import SubCategory
from backend.models.mysql.subcategory import SubCategory as SubCategoryModel


class MySQLSubCategoryRepository(ISubCategoryRepository):
    """MySQL implementation of subcategory repository."""

    def __init__(self, db: Session):
        if db is None:
            raise ValueError("db: Session parameter is required")
        self._db = db

    def get_by_id(self, subcategory_id: int) -> Optional[SubCategory]:
        model = self._db.query(SubCategoryModel).filter(SubCategoryModel.id == subcategory_id).first()
        return self._to_entity(model) if model else None

    def get_by_name(self, name: str) -> Optional[SubCategory]:
        model = self._db.query(SubCategoryModel).filter(SubCategoryModel.name == name).first()
        return self._to_entity(model) if model else None

    def get_by_category_id(self, category_id: int) -> list[SubCategory]:
        models = self._db.query(SubCategoryModel).filter(SubCategoryModel.category_id == category_id).all()
        return [self._to_entity(m) for m in models]

    def get_all(self) -> list[SubCategory]:
        models = self._db.query(SubCategoryModel).all()
        return [self._to_entity(m) for m in models]

    def create(self, subcategory: SubCategory) -> SubCategory:
        model = SubCategoryModel(
            name=subcategory.name,
            category_id=subcategory.category_id,
            is_default=subcategory.is_default,
        )
        self._db.add(model)
        self._db.commit()
        self._db.refresh(model)
        return self._to_entity(model)

    def delete(self, subcategory_id: int) -> bool:
        model = self._db.query(SubCategoryModel).filter(SubCategoryModel.id == subcategory_id).first()
        if not model:
            return False

        self._db.delete(model)
        self._db.commit()
        return True

    @staticmethod
    def _to_entity(model: SubCategoryModel) -> SubCategory:
        return SubCategory(
            id=model.id,
            name=model.name,
            category_id=model.category_id,
            is_default=model.is_default,
        )
