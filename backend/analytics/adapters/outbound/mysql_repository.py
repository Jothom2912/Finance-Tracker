"""
MySQL outbound adapter for Analytics context.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from backend.analytics.application.ports.outbound import IAnalyticsReadRepository
from backend.repositories.mysql.budget_repository import MySQLBudgetRepository
from backend.repositories.mysql.category_repository import MySQLCategoryRepository
from backend.repositories.mysql.transaction_repository import MySQLTransactionRepository


class MySQLAnalyticsReadRepository(IAnalyticsReadRepository):
    def __init__(self, db: Session):
        self._transaction_repo = MySQLTransactionRepository(db)
        self._category_repo = MySQLCategoryRepository(db)
        self._budget_repo = MySQLBudgetRepository(db)

    def get_transactions(
        self,
        account_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 10000,
    ) -> list[dict]:
        return self._transaction_repo.get_all(
            start_date=start_date,
            end_date=end_date,
            account_id=account_id,
            limit=limit,
        )

    def get_categories(self) -> list[dict]:
        return self._category_repo.get_all()

    def get_budgets(self, account_id: int) -> list[dict]:
        return self._budget_repo.get_all(account_id=account_id)
