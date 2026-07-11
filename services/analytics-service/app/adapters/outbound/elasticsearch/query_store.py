"""Læseside: ES-aggregeringer → DTOs.

Aggregerings-semantikken replikerer gatewayens AnalyticsService præcist
(dual-read-verifikationen sammenligner output felt for felt):

- Expense/income-klassifikation følger domain/classification.py, udtrykt
  som ES bool-filtre (type primært, fortegns-fallback for tomme typer).
- Buckets nøgles på category_id/subcategory_id (aldrig navne); labels er
  display-metadata med samme fallbacks som gatewayen
  ("Ukategoriseret"/"(Ingen underkategori)").
- current_account_balance = income − expense + sum(øvrige rå beløb).

Tenant-isolation: hvert query filtrerer user_id + account_id.
"""

from __future__ import annotations

import functools
from collections.abc import Callable, Coroutine
from datetime import date, datetime
from typing import Any, Optional, ParamSpec, TypeVar

from elasticsearch import AsyncElasticsearch
from elasticsearch import exceptions as es_exceptions

from app.adapters.outbound.elasticsearch.mappings import (
    ACCOUNTS_INDEX,
    TRANSACTIONS_INDEX,
    alias_name,
)
from app.application.dto import (
    CategoryDeltaDTO,
    CategoryExpenseDTO,
    FinancialOverviewDTO,
    MonthComparisonDTO,
    MonthlyCashflowDTO,
    MonthlyExpensesDTO,
    SubcategoryExpenseDTO,
    TopMerchantDTO,
    TransactionProjectionDTO,
    TransactionSearchResultDTO,
)
from app.application.ports.outbound import IAnalyticsQueryPort
from app.domain.budget_period import (
    budget_period,
    histogram_bucket_to_budget_month,
    months_in_period,
)
from app.domain.exceptions import ReadStoreUnavailableError

UNCATEGORIZED_LABEL = "Ukategoriseret"
NO_SUBCATEGORY_LABEL = "(Ingen underkategori)"

# terms-agg kan ikke returnere null-keys; -1 er sentinel for "mangler"
# (rigtige ids er positive serials).
MISSING_ID = -1

EXPENSE_FILTER: dict[str, Any] = {
    "bool": {
        "should": [
            {"term": {"transaction_type": "expense"}},
            {
                "bool": {
                    "filter": [
                        {"term": {"transaction_type": ""}},
                        {"range": {"amount": {"lt": 0}}},
                    ]
                }
            },
        ],
        "minimum_should_match": 1,
    }
}

INCOME_FILTER: dict[str, Any] = {
    "bool": {
        "should": [
            {"term": {"transaction_type": "income"}},
            {
                "bool": {
                    "filter": [
                        {"term": {"transaction_type": ""}},
                        {"range": {"amount": {"gt": 0}}},
                    ]
                }
            },
        ],
        "minimum_should_match": 1,
    }
}

OTHER_FILTER: dict[str, Any] = {"bool": {"must_not": [INCOME_FILTER, EXPENSE_FILTER]}}

T = TypeVar("T")
P = ParamSpec("P")


def _translate_es_errors(
    fn: Callable[P, Coroutine[Any, Any, T]],
) -> Callable[P, Coroutine[Any, Any, T]]:
    @functools.wraps(fn)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        try:
            return await fn(*args, **kwargs)
        except (es_exceptions.ConnectionError, es_exceptions.ConnectionTimeout) as exc:
            raise ReadStoreUnavailableError() from exc

    return wrapper


def _category_key(raw_key: Any) -> Optional[int]:
    key = int(raw_key)
    return None if key == MISSING_ID else key


def _top_hit_name(bucket: dict[str, Any], field: str) -> Optional[str]:
    hits = bucket["latest"]["hits"]["hits"]
    if not hits:
        return None
    value = hits[0]["_source"].get(field)
    return str(value) if value else None


class EsAnalyticsQueryStore(IAnalyticsQueryPort):
    def __init__(self, es: AsyncElasticsearch, index_prefix: str = "") -> None:
        self._es = es
        self._tx_alias = alias_name(index_prefix, TRANSACTIONS_INDEX)
        self._accounts_alias = alias_name(index_prefix, ACCOUNTS_INDEX)

    def _base_filters(
        self,
        user_id: int,
        account_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> list[dict[str, Any]]:
        filters: list[dict[str, Any]] = [
            {"term": {"user_id": user_id}},
            {"term": {"account_id": account_id}},
            {"term": {"is_deleted": False}},
        ]
        if start_date or end_date:
            date_range: dict[str, str] = {}
            if start_date:
                date_range["gte"] = start_date.isoformat()
            if end_date:
                date_range["lte"] = end_date.isoformat()
            filters.append({"range": {"tx_date": date_range}})
        return filters

    @staticmethod
    def _category_breakdown_aggs() -> dict[str, Any]:
        return {
            "by_category": {
                "terms": {
                    "field": "category_id",
                    "missing": MISSING_ID,
                    "size": 200,
                    "order": {"sum_abs": "desc"},
                },
                "aggs": {
                    "sum_abs": {"sum": {"field": "amount_abs"}},
                    "latest": {
                        "top_hits": {
                            "size": 1,
                            "_source": ["category_name"],
                            "sort": [{"updated_at": {"order": "desc"}}],
                        }
                    },
                    "by_subcategory": {
                        "terms": {
                            "field": "subcategory_id",
                            "missing": MISSING_ID,
                            "size": 200,
                            "order": {"sum_abs": "desc"},
                        },
                        "aggs": {
                            "sum_abs": {"sum": {"field": "amount_abs"}},
                            "latest": {
                                "top_hits": {
                                    "size": 1,
                                    "_source": ["subcategory_name"],
                                    "sort": [{"updated_at": {"order": "desc"}}],
                                }
                            },
                        },
                    },
                },
            }
        }

    @staticmethod
    def _buckets_to_category_expenses(
        category_buckets: list[dict[str, Any]],
    ) -> list[CategoryExpenseDTO]:
        expenses = []
        for bucket in category_buckets:
            category_id = _category_key(bucket["key"])
            name = _top_hit_name(bucket, "category_name") or UNCATEGORIZED_LABEL
            subcategories = []
            for sub_bucket in bucket["by_subcategory"]["buckets"]:
                subcategory_id = _category_key(sub_bucket["key"])
                sub_name = _top_hit_name(sub_bucket, "subcategory_name") or NO_SUBCATEGORY_LABEL
                subcategories.append(
                    SubcategoryExpenseDTO(
                        subcategory_id=subcategory_id,
                        subcategory_name=sub_name,
                        amount=round(sub_bucket["sum_abs"]["value"], 2),
                    )
                )
            subcategories.sort(key=lambda s: s.amount, reverse=True)
            expenses.append(
                CategoryExpenseDTO(
                    category_id=category_id,
                    category_name=name,
                    amount=round(bucket["sum_abs"]["value"], 2),
                    subcategories=subcategories,
                )
            )
        expenses.sort(key=lambda e: e.amount, reverse=True)
        return expenses

    @_translate_es_errors
    async def financial_overview(
        self,
        *,
        user_id: int,
        account_id: int,
        start_date: date,
        end_date: date,
    ) -> FinancialOverviewDTO:
        response = await self._es.search(
            index=self._tx_alias,
            size=0,
            query={"bool": {"filter": self._base_filters(user_id, account_id, start_date, end_date)}},
            aggs={
                "income": {
                    "filter": INCOME_FILTER,
                    "aggs": {"sum_abs": {"sum": {"field": "amount_abs"}}},
                },
                "expense": {
                    "filter": EXPENSE_FILTER,
                    "aggs": {
                        "sum_abs": {"sum": {"field": "amount_abs"}},
                        **self._category_breakdown_aggs(),
                    },
                },
                "other": {
                    "filter": OTHER_FILTER,
                    "aggs": {"sum_raw": {"sum": {"field": "amount"}}},
                },
            },
        )
        aggs = response["aggregations"]
        total_income = aggs["income"]["sum_abs"]["value"]
        total_expenses = aggs["expense"]["sum_abs"]["value"]
        other_raw = aggs["other"]["sum_raw"]["value"]

        current_account_balance = total_income - total_expenses + other_raw
        average = total_expenses / months_in_period(start_date, end_date)

        return FinancialOverviewDTO(
            start_date=start_date,
            end_date=end_date,
            total_income=round(total_income, 2),
            total_expenses=round(total_expenses, 2),
            net_change_in_period=round(total_income - total_expenses, 2),
            expenses_by_category=self._buckets_to_category_expenses(aggs["expense"]["by_category"]["buckets"]),
            current_account_balance=round(current_account_balance, 2),
            average_monthly_expenses=round(average, 2),
        )

    @_translate_es_errors
    async def expenses_by_month(
        self,
        *,
        user_id: int,
        account_id: int,
        start_date: date,
        end_date: date,
        budget_start_day: int,
    ) -> list[MonthlyExpensesDTO]:
        response = await self._es.search(
            index=self._tx_alias,
            size=0,
            query={"bool": {"filter": self._base_filters(user_id, account_id, start_date, end_date)}},
            aggs={
                "expense": {
                    "filter": EXPENSE_FILTER,
                    "aggs": {
                        "by_month": {
                            "date_histogram": {
                                "field": "tx_date",
                                "calendar_interval": "month",
                                "offset": f"+{budget_start_day - 1}d",
                                "min_doc_count": 1,
                            },
                            "aggs": {"sum_abs": {"sum": {"field": "amount_abs"}}},
                        }
                    },
                },
            },
        )
        results = []
        for bucket in response["aggregations"]["expense"]["by_month"]["buckets"]:
            bucket_start = datetime.fromisoformat(bucket["key_as_string"].replace("Z", "+00:00")).date()
            results.append(
                MonthlyExpensesDTO(
                    month=histogram_bucket_to_budget_month(bucket_start, budget_start_day),
                    total_expenses=round(bucket["sum_abs"]["value"], 2),
                )
            )
        results.sort(key=lambda r: r.month)
        return results

    @_translate_es_errors
    async def cashflow_by_month(
        self,
        *,
        user_id: int,
        account_id: int,
        start_date: date,
        end_date: date,
        budget_start_day: int,
    ) -> list[MonthlyCashflowDTO]:
        response = await self._es.search(
            index=self._tx_alias,
            size=0,
            query={"bool": {"filter": self._base_filters(user_id, account_id, start_date, end_date)}},
            aggs={
                "by_month": {
                    "date_histogram": {
                        "field": "tx_date",
                        "calendar_interval": "month",
                        "offset": f"+{budget_start_day - 1}d",
                        "min_doc_count": 0,
                        "extended_bounds": {
                            "min": start_date.isoformat(),
                            "max": end_date.isoformat(),
                        },
                    },
                    "aggs": {
                        "income": {
                            "filter": INCOME_FILTER,
                            "aggs": {"sum_abs": {"sum": {"field": "amount_abs"}}},
                        },
                        "expense": {
                            "filter": EXPENSE_FILTER,
                            "aggs": {"sum_abs": {"sum": {"field": "amount_abs"}}},
                        },
                    },
                }
            },
        )
        results = []
        for bucket in response["aggregations"]["by_month"]["buckets"]:
            bucket_start = datetime.fromisoformat(bucket["key_as_string"].replace("Z", "+00:00")).date()
            income = round(bucket["income"]["sum_abs"]["value"], 2)
            expenses = round(bucket["expense"]["sum_abs"]["value"], 2)
            results.append(
                MonthlyCashflowDTO(
                    month=histogram_bucket_to_budget_month(bucket_start, budget_start_day),
                    total_income=income,
                    total_expenses=expenses,
                    net=round(income - expenses, 2),
                )
            )
        results.sort(key=lambda r: r.month)
        return results

    @_translate_es_errors
    async def month_comparison(
        self,
        *,
        user_id: int,
        account_id: int,
        year: int,
        month: int,
        budget_start_day: int,
    ) -> MonthComparisonDTO:
        prev_year, prev_month = (year, month - 1) if month > 1 else (year - 1, 12)
        current_start, current_end = budget_period(year, month, budget_start_day)
        previous_start, previous_end = budget_period(prev_year, prev_month, budget_start_day)

        def period_agg(start: date, end: date) -> dict[str, Any]:
            return {
                "filter": {
                    "bool": {
                        "filter": [
                            {
                                "range": {
                                    "tx_date": {
                                        "gte": start.isoformat(),
                                        "lte": end.isoformat(),
                                    }
                                }
                            },
                            EXPENSE_FILTER,
                        ]
                    }
                },
                "aggs": {
                    "sum_abs": {"sum": {"field": "amount_abs"}},
                    **self._category_breakdown_aggs(),
                },
            }

        response = await self._es.search(
            index=self._tx_alias,
            size=0,
            query={"bool": {"filter": self._base_filters(user_id, account_id, previous_start, current_end)}},
            aggs={
                "current": period_agg(current_start, current_end),
                "previous": period_agg(previous_start, previous_end),
            },
        )
        aggs = response["aggregations"]

        def bucket_map(period: dict[str, Any]) -> dict[Optional[int], tuple[str, float]]:
            result: dict[Optional[int], tuple[str, float]] = {}
            for bucket in period["by_category"]["buckets"]:
                category_id = _category_key(bucket["key"])
                name = _top_hit_name(bucket, "category_name") or UNCATEGORIZED_LABEL
                result[category_id] = (name, round(bucket["sum_abs"]["value"], 2))
            return result

        current_map = bucket_map(aggs["current"])
        previous_map = bucket_map(aggs["previous"])

        deltas = []
        for category_id in current_map.keys() | previous_map.keys():
            name = (current_map.get(category_id) or previous_map[category_id])[0]
            current_amount = current_map.get(category_id, (name, 0.0))[1]
            previous_amount = previous_map.get(category_id, (name, 0.0))[1]
            change = round(current_amount - previous_amount, 2)
            change_percent = round(change / previous_amount * 100, 1) if previous_amount else None
            deltas.append(
                CategoryDeltaDTO(
                    category_id=category_id,
                    category_name=name,
                    current_amount=current_amount,
                    previous_amount=previous_amount,
                    change_amount=change,
                    change_percent=change_percent,
                )
            )
        deltas.sort(key=lambda d: abs(d.change_amount), reverse=True)

        return MonthComparisonDTO(
            month=month,
            year=year,
            previous_month=prev_month,
            previous_year=prev_year,
            total_current=round(aggs["current"]["sum_abs"]["value"], 2),
            total_previous=round(aggs["previous"]["sum_abs"]["value"], 2),
            deltas=deltas,
        )

    @_translate_es_errors
    async def search_transactions(
        self,
        *,
        user_id: int,
        account_id: int,
        search: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        category_id: Optional[int] = None,
        tx_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> TransactionSearchResultDTO:
        filters = self._base_filters(user_id, account_id, start_date, end_date)
        if category_id is not None:
            filters.append({"term": {"category_id": category_id}})
        if tx_type is not None:
            # Eksakt type-match (paritet med gatewayens transaktionsliste,
            # som ikke bruger fortegns-fallback ved filtrering).
            filters.append({"term": {"transaction_type": tx_type.strip().lower()}})

        query: dict[str, Any] = {"bool": {"filter": filters}}
        if search and search.strip():
            query["bool"]["must"] = [{"match": {"description": {"query": search.strip(), "operator": "and"}}}]

        response = await self._es.search(
            index=self._tx_alias,
            query=query,
            sort=[
                {"tx_date": {"order": "desc"}},
                {"transaction_id": {"order": "desc"}},
            ],
            from_=offset,
            size=limit,
            track_total_hits=True,
        )
        items = []
        for hit in response["hits"]["hits"]:
            source = hit["_source"]
            items.append(
                TransactionProjectionDTO(
                    id=source["transaction_id"],
                    amount=source["amount"],
                    description=source.get("description"),
                    date=date.fromisoformat(source["tx_date"]),
                    type=source.get("transaction_type", ""),
                    category_id=source.get("category_id"),
                    category_name=source.get("category_name"),
                    subcategory_id=source.get("subcategory_id"),
                    subcategory_name=source.get("subcategory_name"),
                    account_id=source["account_id"],
                    categorization_tier=source.get("categorization_tier"),
                )
            )
        return TransactionSearchResultDTO(
            total_count=int(response["hits"]["total"]["value"]),
            items=items,
        )

    @_translate_es_errors
    async def top_merchants(
        self,
        *,
        user_id: int,
        account_id: int,
        start_date: date,
        end_date: date,
        limit: int = 10,
    ) -> list[TopMerchantDTO]:
        response = await self._es.search(
            index=self._tx_alias,
            size=0,
            query={"bool": {"filter": self._base_filters(user_id, account_id, start_date, end_date)}},
            aggs={
                "expense": {
                    "filter": EXPENSE_FILTER,
                    "aggs": {
                        "by_merchant": {
                            "terms": {
                                "field": "description.raw",
                                "size": limit,
                                "order": {"sum_abs": "desc"},
                            },
                            "aggs": {"sum_abs": {"sum": {"field": "amount_abs"}}},
                        }
                    },
                }
            },
        )
        return [
            TopMerchantDTO(
                description=str(bucket["key"]),
                total_amount=round(bucket["sum_abs"]["value"], 2),
                transaction_count=int(bucket["doc_count"]),
            )
            for bucket in response["aggregations"]["expense"]["by_merchant"]["buckets"]
        ]

    @_translate_es_errors
    async def get_budget_start_day(self, *, user_id: int, account_id: int) -> Optional[int]:
        try:
            doc = await self._es.get(index=self._accounts_alias, id=str(account_id))
        except es_exceptions.NotFoundError:
            return None
        source = doc["_source"]
        if int(source.get("user_id", MISSING_ID)) != user_id:
            # Tenant-isolation: fremmed konto behandles som ukendt.
            return None
        value = source.get("budget_start_day")
        return int(value) if value is not None else None
