"""
Anti-corruption layer adapter for Transaction domain.
Provides expense data for budget summary calculations.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from backend.models.mysql.transaction import Transaction as TransactionModel
from backend.monthly_budget.application.ports.outbound import ITransactionPort


class MySQLTransactionAdapter(ITransactionPort):
    """Reads expense totals per category for a given date range."""

    def __init__(self, db: Session):
        self._db = db

    def get_expenses_by_category(
        self, account_id: int, start_date: date, end_date: date
    ) -> dict[int, float]:
        rows = (
            self._db.query(
                TransactionModel.Category_idCategory,
                sa_func.sum(sa_func.abs(TransactionModel.amount)),
            )
            .filter(
                TransactionModel.Account_idAccount == account_id,
                TransactionModel.type == "expense",
                TransactionModel.date >= start_date,
                TransactionModel.date <= end_date,
            )
            .group_by(TransactionModel.Category_idCategory)
            .all()
        )

        return {int(cat_id): float(total) for cat_id, total in rows if cat_id}
