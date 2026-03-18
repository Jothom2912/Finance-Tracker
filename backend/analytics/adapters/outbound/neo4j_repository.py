"""
Transitional read model for analytics — Neo4j backend.

This adapter performs direct Cypher queries.
Exit-plan: replace with projections via event bus (RabbitMQ)
when microservice-split is implemented.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Optional

from backend.analytics.application.ports.outbound import IAnalyticsReadRepository
from backend.database.neo4j import get_neo4j_driver

logger = logging.getLogger(__name__)


def _to_python_date(value: Any) -> Any:
    """Convert Neo4j date types to Python date."""
    if value is None:
        return None
    if hasattr(value, "to_native"):
        native = value.to_native()
        if isinstance(native, datetime):
            return native.date()
        return native
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).date()
        except ValueError:
            return value
    return value


class Neo4jAnalyticsReadRepository(IAnalyticsReadRepository):
    def __init__(self, driver: Any = None) -> None:
        self._driver = driver or get_neo4j_driver()

    def get_transactions(
        self,
        account_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 10000,
    ) -> list[dict]:
        query = (
            "MATCH (a:Account)-[:HAS_TRANSACTION]->(t:Transaction)"
            "-[:BELONGS_TO_CATEGORY]->(c:Category)"
            " WHERE a.idAccount = $account_id"
        )
        params: dict[str, Any] = {"account_id": account_id, "limit": limit}

        if start_date:
            query += " AND t.date >= $start_date"
            params["start_date"] = start_date.isoformat()
        if end_date:
            query += " AND t.date <= $end_date"
            params["end_date"] = end_date.isoformat()

        query += " RETURN t, c, a ORDER BY t.date DESC LIMIT $limit"

        try:
            with self._driver.session() as session:
                result = session.run(query, **params)
                return [self._record_to_dict(r) for r in result]
        except Exception as e:
            logger.error("Neo4j analytics get_transactions error: %s", e)
            return []

    def get_categories(self) -> list[dict]:
        try:
            with self._driver.session() as session:
                result = session.run("MATCH (c:Category) RETURN c")
                return [
                    {
                        "idCategory": r["c"].get("idCategory"),
                        "name": r["c"].get("name"),
                        "type": r["c"].get("type"),
                    }
                    for r in result
                ]
        except Exception as e:
            logger.error("Neo4j analytics get_categories error: %s", e)
            return []

    def get_budgets(self, account_id: int) -> list[dict]:
        query = "MATCH (a:Account)-[:HAS_BUDGET]->(b:Budget) WHERE a.idAccount = $account_id RETURN b"
        try:
            with self._driver.session() as session:
                result = session.run(query, account_id=account_id)
                return [
                    {
                        "idBudget": r["b"].get("idBudget"),
                        "amount": r["b"].get("amount", 0.0),
                        "budget_date": r["b"].get("budget_date"),
                        "Account_idAccount": account_id,
                        "Category_idCategory": r["b"].get("Category_idCategory"),
                    }
                    for r in result
                ]
        except Exception as e:
            logger.error("Neo4j analytics get_budgets error: %s", e)
            return []

    @staticmethod
    def _record_to_dict(record: Any) -> dict:
        t = record["t"]
        return {
            "idTransaction": t.get("idTransaction"),
            "amount": t.get("amount", 0.0),
            "description": t.get("description"),
            "date": _to_python_date(t.get("date")),
            "type": t.get("type"),
            "Category_idCategory": record["c"].get("idCategory"),
            "Account_idAccount": record["a"].get("idAccount"),
        }
