"""Read-only MySQL adapter for the Category projection.

Writes to ``Category`` belong in
:class:`backend.consumers.category_sync.CategorySyncConsumer` —
this adapter deliberately exposes no ``create``/``update``/``delete``
so no one can accidentally split the state from transaction-service.
"""

from typing import Optional

from sqlalchemy.orm import Session

from backend.category.application.ports.outbound import ICategoryRepository
from backend.category.domain.entities import Category
from backend.category.domain.value_objects import CategoryType
from backend.models.mysql.category import Category as CategoryModel


class MySQLCategoryRepository(ICategoryRepository):
    """Read-only MySQL implementation of the Category port."""

    def __init__(self, db: Session):
        if db is None:
            raise ValueError("db: Session parameter is required")
        self._db = db

    def get_by_id(self, category_id: int) -> Optional[Category]:
        model = self._db.query(CategoryModel).filter(CategoryModel.idCategory == category_id).first()
        return self._to_entity(model) if model else None

    def get_by_name(self, name: str) -> Optional[Category]:
        model = self._db.query(CategoryModel).filter(CategoryModel.name == name).first()
        return self._to_entity(model) if model else None

    def get_all(self) -> list[Category]:
        models = self._db.query(CategoryModel).order_by(CategoryModel.display_order).all()
        return [self._to_entity(m) for m in models]

    @staticmethod
    def _to_entity(model: CategoryModel) -> Category:
        try:
            cat_type = CategoryType(model.type)
        except (ValueError, KeyError):
            cat_type = CategoryType.EXPENSE

        return Category(
            id=model.idCategory,
            name=model.name,
            type=cat_type,
            display_order=model.display_order or 0,
        )
