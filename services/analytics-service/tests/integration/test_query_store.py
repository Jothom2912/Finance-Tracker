"""Golden-tests: EsAnalyticsQueryStore skal give PRÆCIS gatewayens tal.

Datasættet er en 1:1-kopi af gatewayens FakeAnalyticsReadRepository
(services/gateway-service/tests/unit/test_analytics_service.py), oversat
til event-konventionen (positive beløb + transaction_type). De
forventede tal er gateway-unit-testenes assertions — det gør dual-read-
enighed bevislig, før dual-read overhovedet kører.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

import pytest
from app.adapters.outbound.elasticsearch.bootstrap import ensure_indices
from app.adapters.outbound.elasticsearch.guarded_upsert import guarded_full_state_upsert
from app.adapters.outbound.elasticsearch.mappings import alias_name
from app.adapters.outbound.elasticsearch.query_store import EsAnalyticsQueryStore
from app.adapters.outbound.elasticsearch.transaction_store import (
    EsTransactionProjectionStore,
)
from elasticsearch import AsyncElasticsearch

TS = int(datetime(2026, 6, 10, tzinfo=timezone.utc).timestamp() * 1000)
USER_ID = 7
ACCOUNT_ID = 1

GOLDEN_ROWS: list[dict[str, Any]] = [
    {
        "transaction_id": 1,
        "amount": 1000.0,
        "description": "Salary",
        "tx_date": date(2026, 6, 1),
        "transaction_type": "income",
        "category_id": None,
        "category_name": None,
        "subcategory_id": None,
        "subcategory_name": None,
        "categorization_tier": None,
    },
    {
        "transaction_id": 2,
        "amount": 200.0,
        "description": "Groceries",
        "tx_date": date(2026, 6, 2),
        "transaction_type": "expense",
        "category_id": 10,
        "category_name": "Food",
        "subcategory_id": 101,
        "subcategory_name": "Dagligvarer",
        "categorization_tier": "rule",
    },
    {
        "transaction_id": 3,
        "amount": 50.0,
        "description": "Bus",
        "tx_date": date(2026, 6, 3),
        "transaction_type": "expense",
        "category_id": None,
        "category_name": None,
        "subcategory_id": None,
        "subcategory_name": None,
        "categorization_tier": None,
    },
    {
        "transaction_id": 4,
        "amount": 100.0,
        "description": "Wolt",
        "tx_date": date(2026, 6, 4),
        "transaction_type": "expense",
        "category_id": 10,
        "category_name": "Food",
        "subcategory_id": 102,
        "subcategory_name": "Takeaway",
        "categorization_tier": "rule",
    },
    {
        "transaction_id": 5,
        "amount": 25.0,
        "description": "Manual food expense",
        "tx_date": date(2026, 6, 5),
        "transaction_type": "expense",
        "category_id": 10,
        "category_name": "Food",
        "subcategory_id": None,
        "subcategory_name": None,
        "categorization_tier": "manual",
    },
]


async def seed_transactions(
    store: EsTransactionProjectionStore,
    rows: list[dict[str, Any]],
    *,
    user_id: int = USER_ID,
    account_id: int = ACCOUNT_ID,
) -> None:
    for row in rows:
        await store.upsert_core(
            transaction_id=row["transaction_id"],
            account_id=account_id,
            user_id=user_id,
            amount=row["amount"],
            transaction_type=row["transaction_type"],
            tx_date=row["tx_date"],
            description=row["description"],
            category_id=row["category_id"],
            category_name=row["category_name"],
            subcategory_id=row["subcategory_id"],
            subcategory_name=row["subcategory_name"],
            categorization_tier=row["categorization_tier"],
            categorization_confidence=None,
            event_ts=TS,
        )


@pytest.fixture
async def query_store(es: AsyncElasticsearch, index_prefix: str) -> EsAnalyticsQueryStore:
    await ensure_indices(es, index_prefix)
    tx_store = EsTransactionProjectionStore(es, index_prefix)
    await seed_transactions(tx_store, GOLDEN_ROWS)
    await es.indices.refresh(index=alias_name(index_prefix, "transactions"))
    return EsAnalyticsQueryStore(es, index_prefix)


JUNE = {"start_date": date(2026, 6, 1), "end_date": date(2026, 6, 30)}


class TestGoldenFinancialOverview:
    async def test_totals_match_gateway_expectations(self, query_store: EsAnalyticsQueryStore) -> None:
        overview = await query_store.financial_overview(user_id=USER_ID, account_id=ACCOUNT_ID, **JUNE)

        assert overview.total_income == 1000
        assert overview.total_expenses == 375
        assert overview.net_change_in_period == 625
        assert overview.current_account_balance == 625
        assert overview.average_monthly_expenses == 375.0

    async def test_category_buckets_match_gateway_expectations(self, query_store: EsAnalyticsQueryStore) -> None:
        overview = await query_store.financial_overview(user_id=USER_ID, account_id=ACCOUNT_ID, **JUNE)

        by_id = {e.category_id: e for e in overview.expenses_by_category}
        assert set(by_id.keys()) == {10, None}

        food = by_id[10]
        assert food.category_name == "Food"
        assert food.amount == 325

        subs = {s.subcategory_id: s for s in food.subcategories}
        assert subs[101].amount == 200
        assert subs[101].subcategory_name == "Dagligvarer"
        assert subs[102].amount == 100
        assert subs[None].amount == 25
        assert subs[None].subcategory_name == "(Ingen underkategori)"

        uncategorized = by_id[None]
        assert uncategorized.category_name == "Ukategoriseret"
        assert uncategorized.amount == 50

    async def test_categories_sorted_by_amount_desc(self, query_store: EsAnalyticsQueryStore) -> None:
        overview = await query_store.financial_overview(user_id=USER_ID, account_id=ACCOUNT_ID, **JUNE)
        amounts = [e.amount for e in overview.expenses_by_category]
        assert amounts == sorted(amounts, reverse=True)


class TestTenantIsolationAndSoftDelete:
    async def test_other_users_data_is_invisible(self, query_store: EsAnalyticsQueryStore) -> None:
        overview = await query_store.financial_overview(user_id=999, account_id=ACCOUNT_ID, **JUNE)
        assert overview.total_income == 0
        assert overview.total_expenses == 0
        assert overview.expenses_by_category == []

    async def test_deleted_transactions_are_excluded(
        self,
        es: AsyncElasticsearch,
        index_prefix: str,
        query_store: EsAnalyticsQueryStore,
    ) -> None:
        tx_store = EsTransactionProjectionStore(es, index_prefix)
        await tx_store.mark_deleted(transaction_id=2, event_ts=TS + 1)
        await es.indices.refresh(index=alias_name(index_prefix, "transactions"))

        overview = await query_store.financial_overview(user_id=USER_ID, account_id=ACCOUNT_ID, **JUNE)
        assert overview.total_expenses == 175  # 375 - 200 (Groceries slettet)


class TestExpensesByMonth:
    async def test_start_day_1_buckets_by_calendar_month(self, query_store: EsAnalyticsQueryStore) -> None:
        result = await query_store.expenses_by_month(
            user_id=USER_ID,
            account_id=ACCOUNT_ID,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            budget_start_day=1,
        )
        assert [(r.month, r.total_expenses) for r in result] == [("2026-06", 375.0)]

    async def test_start_day_15_splits_across_budget_months(
        self,
        es: AsyncElasticsearch,
        index_prefix: str,
        query_store: EsAnalyticsQueryStore,
    ) -> None:
        # Tilføj en udgift d. 20/6 — med start_day 15 hører den til
        # budgetmåned juli, mens dagene 1.-5. juni hører til juni.
        tx_store = EsTransactionProjectionStore(es, index_prefix)
        await seed_transactions(
            tx_store,
            [
                {
                    "transaction_id": 6,
                    "amount": 60.0,
                    "description": "Sen juni-udgift",
                    "tx_date": date(2026, 6, 20),
                    "transaction_type": "expense",
                    "category_id": None,
                    "category_name": None,
                    "subcategory_id": None,
                    "subcategory_name": None,
                    "categorization_tier": None,
                }
            ],
        )
        await es.indices.refresh(index=alias_name(index_prefix, "transactions"))

        result = await query_store.expenses_by_month(
            user_id=USER_ID,
            account_id=ACCOUNT_ID,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            budget_start_day=15,
        )
        assert [(r.month, r.total_expenses) for r in result] == [
            ("2026-06", 375.0),
            ("2026-07", 60.0),
        ]


class TestCashflowByMonth:
    async def test_dense_window_zero_fills_empty_months(self, query_store: EsAnalyticsQueryStore) -> None:
        result = await query_store.cashflow_by_month(
            user_id=USER_ID,
            account_id=ACCOUNT_ID,
            start_date=date(2026, 5, 1),
            end_date=date(2026, 7, 31),
            budget_start_day=1,
        )
        assert [r.month for r in result] == ["2026-05", "2026-06", "2026-07"]
        may, june, july = result
        assert (may.total_income, may.total_expenses, may.net) == (0.0, 0.0, 0.0)
        assert (june.total_income, june.total_expenses, june.net) == (1000.0, 375.0, 625.0)
        assert (july.total_income, july.total_expenses, july.net) == (0.0, 0.0, 0.0)


class TestMonthComparison:
    async def test_deltas_between_budget_months(
        self,
        es: AsyncElasticsearch,
        index_prefix: str,
        query_store: EsAnalyticsQueryStore,
    ) -> None:
        # Maj: Food 100. Juni: Food 325 + Ukategoriseret 50 (golden).
        tx_store = EsTransactionProjectionStore(es, index_prefix)
        await seed_transactions(
            tx_store,
            [
                {
                    "transaction_id": 7,
                    "amount": 100.0,
                    "description": "Maj-indkøb",
                    "tx_date": date(2026, 5, 10),
                    "transaction_type": "expense",
                    "category_id": 10,
                    "category_name": "Food",
                    "subcategory_id": None,
                    "subcategory_name": None,
                    "categorization_tier": "rule",
                }
            ],
        )
        await es.indices.refresh(index=alias_name(index_prefix, "transactions"))

        comparison = await query_store.month_comparison(
            user_id=USER_ID, account_id=ACCOUNT_ID, year=2026, month=6, budget_start_day=1
        )

        assert comparison.total_current == 375.0
        assert comparison.total_previous == 100.0
        deltas = {d.category_id: d for d in comparison.deltas}

        food = deltas[10]
        assert (food.current_amount, food.previous_amount) == (325.0, 100.0)
        assert food.change_amount == 225.0
        assert food.change_percent == 225.0

        new_bucket = deltas[None]
        assert new_bucket.previous_amount == 0.0
        assert new_bucket.change_percent is None  # "Ny" i UI'et

        # Sorteret på |ændring| — Food (225) før Ukategoriseret (50).
        assert comparison.deltas[0].category_id == 10


class TestSearchTransactions:
    async def test_danish_stemming_matches_inflected_query(
        self,
        es: AsyncElasticsearch,
        index_prefix: str,
        query_store: EsAnalyticsQueryStore,
    ) -> None:
        tx_store = EsTransactionProjectionStore(es, index_prefix)
        await seed_transactions(
            tx_store,
            [
                {
                    "transaction_id": 8,
                    "amount": 250.0,
                    "description": "Tryg forsikring betaling",
                    "tx_date": date(2026, 6, 15),
                    "transaction_type": "expense",
                    "category_id": None,
                    "category_name": None,
                    "subcategory_id": None,
                    "subcategory_name": None,
                    "categorization_tier": None,
                }
            ],
        )
        await es.indices.refresh(index=alias_name(index_prefix, "transactions"))

        result = await query_store.search_transactions(user_id=USER_ID, account_id=ACCOUNT_ID, search="forsikringen")
        assert result.total_count == 1
        assert result.items[0].id == 8

    async def test_filters_and_canonical_sort_order(self, query_store: EsAnalyticsQueryStore) -> None:
        result = await query_store.search_transactions(
            user_id=USER_ID, account_id=ACCOUNT_ID, category_id=10, tx_type="expense"
        )
        assert result.total_count == 3
        # Kanonisk orden: tx_date desc, transaction_id desc.
        assert [t.id for t in result.items] == [5, 4, 2]

    async def test_pagination_reports_full_total(self, query_store: EsAnalyticsQueryStore) -> None:
        result = await query_store.search_transactions(user_id=USER_ID, account_id=ACCOUNT_ID, limit=2, offset=0)
        assert result.total_count == 5
        assert len(result.items) == 2

    async def test_amount_desc_sorts_on_amount_abs(self, query_store: EsAnalyticsQueryStore) -> None:
        # AI-19: largest_expense-intentens serverside-sortering.
        result = await query_store.search_transactions(
            user_id=USER_ID, account_id=ACCOUNT_ID, tx_type="expense", sort="amount_desc"
        )
        assert [t.id for t in result.items] == [2, 4, 3, 5]


class TestBudgetStartDayLookup:
    async def test_reads_from_accounts_projection_with_tenant_check(
        self,
        es: AsyncElasticsearch,
        index_prefix: str,
        query_store: EsAnalyticsQueryStore,
    ) -> None:
        await guarded_full_state_upsert(
            es,
            alias=alias_name(index_prefix, "accounts"),
            doc_id=str(ACCOUNT_ID),
            fields={
                "account_id": ACCOUNT_ID,
                "user_id": USER_ID,
                "name": "Lønkonto",
                "saldo": 1000.0,
                "budget_start_day": 25,
            },
            event_ts=TS,
        )

        assert await query_store.get_budget_start_day(user_id=USER_ID, account_id=ACCOUNT_ID) == 25
        # Fremmed bruger må ikke kunne aflæse kontoens indstillinger.
        assert await query_store.get_budget_start_day(user_id=999, account_id=ACCOUNT_ID) is None
        assert await query_store.get_budget_start_day(user_id=USER_ID, account_id=404) is None
