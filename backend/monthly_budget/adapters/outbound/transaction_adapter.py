"""
Anti-corruption layer adapter for Transaction domain.
Provides expense data for budget summary calculations.
"""
from __future__ import annotations

from calendar import monthrange
from datetime import date

from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from backend.monthly_budget.application.ports.outbound import ITransactionPort
from backend.models.mysql.transaction import Transaction as TransactionModel


class MySQLTransactionAdapter(ITransactionPort):
    """Reads expense totals per category for a given month."""

    def __init__(self, db: Session):
        self._db = db

    def get_expenses_by_category(
        self, account_id: int, month: int, year: int
    ) -> dict[int, float]:
        start = date(year, month, 1)
        _, last_day = monthrange(year, month)
        end = date(year, month, last_day)

        rows = (
            self._db.query(
                TransactionModel.Category_idCategory,
                sa_func.sum(sa_func.abs(TransactionModel.amount)),
            )
            .filter(
                TransactionModel.Account_idAccount == account_id,
                TransactionModel.type == "expense",
                TransactionModel.date >= start,
                TransactionModel.date <= end,
            )
            .group_by(TransactionModel.Category_idCategory)
            .all()
        )

        return {
            int(cat_id): float(total) for cat_id, total in rows if cat_id
        }
