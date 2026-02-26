"""
Anti-corruption layer adapter for Category domain.
Implements the MonthlyBudget domain's ICategoryPort.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from backend.monthly_budget.application.ports.outbound import ICategoryPort
from backend.models.mysql.category import Category as CategoryModel


class MySQLCategoryAdapter(ICategoryPort):
    """MySQL implementation of category port for monthly budget domain."""

    def __init__(self, db: Session):
        self._db = db

    def exists(self, category_id: int) -> bool:
        return (
            self._db.query(CategoryModel)
            .filter(CategoryModel.idCategory == category_id)
            .first()
            is not None
        )

    def get_name(self, category_id: int) -> Optional[str]:
        model = (
            self._db.query(CategoryModel)
            .filter(CategoryModel.idCategory == category_id)
            .first()
        )
        return model.name if model else None

    def get_all_names(self) -> dict[int, str]:
        rows = self._db.query(
            CategoryModel.idCategory, CategoryModel.name
        ).all()
        return {int(row[0]): row[1] for row in rows}
