"""Intent dispatcher — maps ResolvedIntent to data retrieval via ports.

Slot→filter conversion happens here, NOT in adapters. The dispatcher knows
intent semantics (e.g. that "category" slot maps to a category filter, that
"amount_max" becomes {"amount": {"$lte": value}}). Adapters receive pre-built
filters and don't know about intent structure.
"""

from __future__ import annotations

import logging
from typing import Any

import anyio

from app.application.ports.analytics_port import IAnalyticsPort
from app.application.ports.semantic_search_port import ISemanticSearchPort
from app.domain.models import (
    CategoryBreakdownPayload,
    DataKind,
    DataReadyData,
    IntentName,
    ResolvedIntent,
    TransactionListPayload,
)

logger = logging.getLogger(__name__)


async def dispatch(
    intent: ResolvedIntent,
    analytics: IAnalyticsPort,
    search: ISemanticSearchPort,
) -> tuple[DataReadyData, float]:
    """Dispatch an intent to the appropriate data source.

    Returns (data_ready_payload, elapsed_ms) where elapsed_ms comes from
    the adapter's own timing.
    """
    match intent.intent:
        case IntentName.LARGEST_EXPENSE:
            return await _dispatch_largest_expense(intent, analytics)
        case IntentName.CATEGORY_BREAKDOWN:
            return await _dispatch_category_breakdown(intent, analytics)
        case IntentName.TRANSACTION_SEARCH:
            return await _dispatch_transaction_search(intent, search)
        case IntentName.BUDGET_STATUS:
            return await _dispatch_budget_status(intent, analytics)
        case _:
            raise ValueError(f"Unknown intent: {intent.intent!r}")


async def _dispatch_largest_expense(
    intent: ResolvedIntent,
    analytics: IAnalyticsPort,
) -> tuple[DataReadyData, float]:
    category = intent.slots.get("category")
    items, elapsed_ms = await analytics.get_largest_expenses(
        intent.period,
        category=category,
    )

    highlight_id = items[0].id if items else None
    payload = TransactionListPayload(items=items, highlight_id=highlight_id)
    return DataReadyData(kind=DataKind.TRANSACTION_LIST, payload=payload), elapsed_ms


async def _dispatch_category_breakdown(
    intent: ResolvedIntent,
    analytics: IAnalyticsPort,
) -> tuple[DataReadyData, float]:
    items, elapsed_ms = await analytics.get_category_breakdown(intent.period)
    total = sum(item.amount for item in items)
    payload = CategoryBreakdownPayload(items=items, total=total)
    return DataReadyData(kind=DataKind.CATEGORY_BREAKDOWN, payload=payload), elapsed_ms


async def _dispatch_transaction_search(
    intent: ResolvedIntent,
    search: ISemanticSearchPort,
) -> tuple[DataReadyData, float]:
    query = intent.slots.get("query", "")
    filters = _slots_to_filters(intent.slots)

    items, elapsed_ms = await anyio.to_thread.run_sync(
        lambda: search.search(
            query,
            period=intent.period,
            filters=filters if filters else None,
        ),
    )

    payload = TransactionListPayload(items=items)
    return DataReadyData(kind=DataKind.TRANSACTION_LIST, payload=payload), elapsed_ms


async def _dispatch_budget_status(
    intent: ResolvedIntent,
    analytics: IAnalyticsPort,
) -> tuple[DataReadyData, float]:
    budget, elapsed_ms = await analytics.get_budget_status(intent.period)
    return DataReadyData(kind=DataKind.BUDGET_STATUS, payload=budget), elapsed_ms


def _slots_to_filters(slots: dict[str, Any]) -> dict[str, Any]:
    """Convert intent slots to domain-level filters for ISemanticSearchPort.

    This is where intent vocabulary becomes filter vocabulary. The adapter
    then translates these filters into its store-specific query syntax.
    """
    filters: dict[str, Any] = {}

    if "category" in slots:
        filters["category"] = slots["category"]

    if "amount_max" in slots:
        filters["amount"] = {"$lte": float(slots["amount_max"])}

    if "amount_min" in slots:
        filters["amount"] = {"$gte": float(slots["amount_min"])}

    if "is_expense" in slots:
        filters["is_expense"] = bool(slots["is_expense"])

    return filters
