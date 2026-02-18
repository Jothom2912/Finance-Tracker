"""
Anti-corruption layer adapter for Category domain.
Implements the Transaction domain's ICategoryPort.
"""
from typing import Optional

from sqlalchemy.orm import Session

from backend.models.mysql.category import Category as CategoryModel
from backend.transaction.application.ports.outbound import ICategoryPort
from backend.transaction.domain.entities import CategoryInfo


class MySQLCategoryAdapter(ICategoryPort):
    """MySQL implementation of category port for transaction domain."""

    def __init__(self, db: Session):
        if db is None:
            raise ValueError("db: Session parameter is required")
        self._db = db

    def get_by_id(self, category_id: int) -> Optional[CategoryInfo]:
        model = (
            self._db.query(CategoryModel)
            .filter(CategoryModel.idCategory == category_id)
            .first()
        )
        return self._to_info(model) if model else None

    def get_all(self) -> list[CategoryInfo]:
        models = self._db.query(CategoryModel).all()
        return [self._to_info(m) for m in models]

    def create(self, name: str, category_type: str) -> CategoryInfo:
        model = CategoryModel(name=name, type=category_type)
        self._db.add(model)
        self._db.commit()
        self._db.refresh(model)
        return self._to_info(model)

    @staticmethod
    def _to_info(model: CategoryModel) -> CategoryInfo:
        return CategoryInfo(
            id=model.idCategory,
            name=model.name,
            type=model.type,
        )
