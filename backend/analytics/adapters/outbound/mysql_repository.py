"""
Transitional read model for analytics.

This adapter performs direct SQL queries against MySQL.
Exit-plan: replace with projections via event bus (RabbitMQ)
when microservice-split is implemented.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy.orm import Session, joinedload

from backend.analytics.application.ports.outbound import IAnalyticsReadRepository
from backend.models.mysql.budget import Budget as BudgetModel
from backend.models.mysql.category import Category as CategoryModel
from backend.models.mysql.transaction import Transaction as TransactionModel


class MySQLAnalyticsReadRepository(IAnalyticsReadRepository):
    def __init__(self, db: Session):
        self._db = db

    def get_transactions(
        self,
        account_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 10000,
    ) -> list[dict]:
        query = self._db.query(TransactionModel).filter(TransactionModel.Account_idAccount == account_id)
        if start_date:
            query = query.filter(TransactionModel.date >= start_date)
        if end_date:
            query = query.filter(TransactionModel.date <= end_date)

        models = query.order_by(TransactionModel.date.desc()).limit(limit).all()
        return [self._serialize_transaction(m) for m in models]

    def get_categories(self) -> list[dict]:
        models = self._db.query(CategoryModel).all()
        return [
            {
                "idCategory": m.idCategory,
                "name": m.name,
                "type": m.type,
            }
            for m in models
        ]

    def get_budgets(self, account_id: int) -> list[dict]:
        models = (
            self._db.query(BudgetModel)
            .options(joinedload(BudgetModel.categories))
            .filter(BudgetModel.Account_idAccount == account_id)
            .all()
        )
        return [self._serialize_budget(m) for m in models]

    @staticmethod
    def _serialize_transaction(model: TransactionModel) -> dict:
        date_value = None
        if model.date:
            if hasattr(model.date, "date"):
                date_value = model.date.date()
            elif isinstance(model.date, date):
                date_value = model.date

        return {
            "idTransaction": model.idTransaction,
            "amount": float(model.amount) if model.amount else 0.0,
            "description": model.description,
            "date": date_value,
            "type": model.type,
            "Category_idCategory": model.Category_idCategory,
            "Account_idAccount": model.Account_idAccount,
            "created_at": (model.created_at.isoformat() if hasattr(model, "created_at") and model.created_at else None),
        }

    @staticmethod
    def _serialize_budget(model: BudgetModel) -> dict:
        category_id = None
        if hasattr(model, "categories") and model.categories:
            category_id = model.categories[0].idCategory

        return {
            "idBudget": model.idBudget,
            "amount": float(model.amount) if model.amount else 0.0,
            "budget_date": (model.budget_date.isoformat() if model.budget_date else None),
            "Account_idAccount": model.Account_idAccount,
            "Category_idCategory": category_id,
        }
