"""
MySQL adapter for Category repository.
"""
from typing import Optional

from sqlalchemy.orm import Session

from backend.category.application.ports.outbound import ICategoryRepository
from backend.category.domain.entities import Category
from backend.category.domain.value_objects import CategoryType
from backend.models.mysql.category import Category as CategoryModel


class MySQLCategoryRepository(ICategoryRepository):
    """MySQL implementation of category repository."""

    def __init__(self, db: Session):
        if db is None:
            raise ValueError("db: Session parameter is required")
        self._db = db

    def get_by_id(self, category_id: int) -> Optional[Category]:
        model = (
            self._db.query(CategoryModel)
            .filter(CategoryModel.idCategory == category_id)
            .first()
        )
        return self._to_entity(model) if model else None

    def get_by_name(self, name: str) -> Optional[Category]:
        model = (
            self._db.query(CategoryModel)
            .filter(CategoryModel.name == name)
            .first()
        )
        return self._to_entity(model) if model else None

    def get_all(self) -> list[Category]:
        models = self._db.query(CategoryModel).all()
        return [self._to_entity(m) for m in models]

    def create(self, category: Category) -> Category:
        model = CategoryModel(
            name=category.name,
            type=(
                category.type.value
                if isinstance(category.type, CategoryType)
                else category.type
            ),
        )
        self._db.add(model)
        self._db.commit()
        self._db.refresh(model)
        return self._to_entity(model)

    def update(self, category: Category) -> Category:
        model = (
            self._db.query(CategoryModel)
            .filter(CategoryModel.idCategory == category.id)
            .first()
        )

        model.name = category.name
        model.type = (
            category.type.value
            if isinstance(category.type, CategoryType)
            else category.type
        )

        self._db.commit()
        self._db.refresh(model)
        return self._to_entity(model)

    def delete(self, category_id: int) -> bool:
        model = (
            self._db.query(CategoryModel)
            .filter(CategoryModel.idCategory == category_id)
            .first()
        )
        if not model:
            return False

        self._db.delete(model)
        self._db.commit()
        return True

    @staticmethod
    def _to_entity(model: CategoryModel) -> Category:
        # Map DB string to CategoryType enum safely
        try:
            cat_type = CategoryType(model.type)
        except (ValueError, KeyError):
            cat_type = CategoryType.EXPENSE

        return Category(
            id=model.idCategory,
            name=model.name,
            type=cat_type,
        )
