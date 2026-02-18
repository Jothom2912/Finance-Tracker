"""
Elasticsearch outbound adapter for Analytics context.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from backend.analytics.application.ports.outbound import IAnalyticsReadRepository
from backend.repositories.elasticsearch.budget_repository import (
    ElasticsearchBudgetRepository,
)
from backend.repositories.elasticsearch.category_repository import (
    ElasticsearchCategoryRepository,
)
from backend.repositories.elasticsearch.transaction_repository import (
    ElasticsearchTransactionRepository,
)


class ElasticsearchAnalyticsReadRepository(IAnalyticsReadRepository):
    def __init__(self):
        self._transaction_repo = ElasticsearchTransactionRepository()
        self._category_repo = ElasticsearchCategoryRepository()
        self._budget_repo = ElasticsearchBudgetRepository()

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
