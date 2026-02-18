"""
Neo4j outbound adapter for Analytics context.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from backend.analytics.application.ports.outbound import IAnalyticsReadRepository
from backend.repositories.neo4j.budget_repository import Neo4jBudgetRepository
from backend.repositories.neo4j.category_repository import Neo4jCategoryRepository
from backend.repositories.neo4j.transaction_repository import (
    Neo4jTransactionRepository,
)


class Neo4jAnalyticsReadRepository(IAnalyticsReadRepository):
    def __init__(self):
        self._transaction_repo = Neo4jTransactionRepository()
        self._category_repo = Neo4jCategoryRepository()
        self._budget_repo = Neo4jBudgetRepository()

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
