"""
Transitional read model for analytics — Elasticsearch backend.

This adapter performs direct ES queries.
Exit-plan: replace with projections via event bus (RabbitMQ)
when microservice-split is implemented.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Optional

from backend.analytics.application.ports.outbound import IAnalyticsReadRepository
from backend.database.elasticsearch import get_es_client

logger = logging.getLogger(__name__)


class ElasticsearchAnalyticsReadRepository(IAnalyticsReadRepository):
    def __init__(self) -> None:
        self._es = get_es_client()

    def get_transactions(
        self,
        account_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 10000,
    ) -> list[dict]:
        must_clauses: list[dict] = [
            {"term": {"Account_idAccount": account_id}},
        ]
        if start_date:
            must_clauses.append({"range": {"date": {"gte": start_date.isoformat()}}})
        if end_date:
            must_clauses.append({"range": {"date": {"lte": end_date.isoformat()}}})

        try:
            response = self._es.search(
                index="transactions",
                query={"bool": {"must": must_clauses}},
                sort=[{"date": "desc"}],
                size=limit,
            )
            results: list[dict] = []
            for hit in response["hits"]["hits"]:
                source = hit["_source"].copy()
                if "idTransaction" not in source or source.get("idTransaction") is None:
                    try:
                        source["idTransaction"] = int(hit["_id"])
                    except (ValueError, TypeError):
                        continue
                self._normalize_date(source)
                results.append(source)
            return results
        except Exception as e:
            logger.error("ES analytics get_transactions error: %s", e)
            return []

    def get_categories(self) -> list[dict]:
        try:
            response = self._es.search(
                index="categories",
                query={"match_all": {}},
                size=10000,
            )
            results: list[dict] = []
            for hit in response["hits"]["hits"]:
                source = hit["_source"].copy()
                if "idCategory" not in source or source.get("idCategory") is None:
                    try:
                        source["idCategory"] = int(hit["_id"])
                    except (ValueError, TypeError):
                        continue
                results.append(source)
            return results
        except Exception as e:
            logger.error("ES analytics get_categories error: %s", e)
            return []

    def get_budgets(self, account_id: int) -> list[dict]:
        try:
            response = self._es.search(
                index="budgets",
                query={"bool": {"must": [{"term": {"Account_idAccount": account_id}}]}},
                size=10000,
            )
            results: list[dict] = []
            for hit in response["hits"]["hits"]:
                source = hit["_source"].copy()
                if "idBudget" not in source or source.get("idBudget") is None:
                    try:
                        source["idBudget"] = int(hit["_id"])
                    except (ValueError, TypeError):
                        continue
                results.append(source)
            return results
        except Exception as e:
            logger.error("ES analytics get_budgets error: %s", e)
            return []

    @staticmethod
    def _normalize_date(source: dict) -> None:
        """Ensure 'date' field is a Python date object."""
        raw = source.get("date")
        if raw is None:
            return
        if isinstance(raw, date) and not isinstance(raw, datetime):
            return
        if isinstance(raw, datetime):
            source["date"] = raw.date()
            return
        if isinstance(raw, str):
            try:
                source["date"] = datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
            except ValueError:
                try:
                    source["date"] = datetime.strptime(raw, "%Y-%m-%d").date()
                except ValueError:
                    source["date"] = None
