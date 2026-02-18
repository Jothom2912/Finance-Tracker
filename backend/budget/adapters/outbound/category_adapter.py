"""
Anti-corruption layer adapter for Category domain.
Implements the Budget domain's ICategoryPort.
"""
from sqlalchemy.orm import Session

from backend.budget.application.ports.outbound import ICategoryPort
from backend.models.mysql.category import Category as CategoryModel


class MySQLCategoryAdapter(ICategoryPort):
    """MySQL implementation of category port for budget domain."""

    def __init__(self, db: Session):
        self._db = db

    def exists(self, category_id: int) -> bool:
        return (
            self._db.query(CategoryModel)
            .filter(CategoryModel.idCategory == category_id)
            .first()
            is not None
        )
