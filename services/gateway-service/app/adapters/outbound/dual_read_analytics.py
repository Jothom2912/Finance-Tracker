"""Dual-read verifikation før cutover (jf. dual-consume-konventionen).

Serverer ALTID primary-resultatet (legacy) og skygge-læser analytics-
service; divergenser logges som ét struktureret WARNING med felt-sti-
diffs. Skygge-fejl propagerer aldrig — verifikationen må ikke koste
oppetid.

Normalisering før sammenligning: floats med ±0.01-tolerance (legacy
summerer float64, ES summerer scaled_float — eksakthed er dækket af
golden-integrationstests i analytics-service), kategorier/subkategorier
sorteret deterministisk. Transaktionslisten sammenlignes på id-sæt:
ordens-divergens ved limit-trunkering er en kendt, dokumenteret klasse
(legacy = ankomstorden, analytics = kanonisk dato/id-orden).
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from app.application.dto import FinancialOverview, MonthlyExpenses, TransactionProjection
from app.application.ports.outbound import IFinancialAnalyticsPort

logger = logging.getLogger(__name__)

FLOAT_TOLERANCE = 0.01


def _floats_differ(a: Optional[float], b: Optional[float]) -> bool:
    if a is None or b is None:
        return a is not b
    return abs(a - b) > FLOAT_TOLERANCE


def diff_overviews(primary: FinancialOverview, shadow: FinancialOverview) -> list[str]:
    diffs: list[str] = []
    for field in (
        "start_date",
        "end_date",
        "total_income",
        "total_expenses",
        "net_change_in_period",
        "current_account_balance",
        "average_monthly_expenses",
    ):
        a, b = getattr(primary, field), getattr(shadow, field)
        if isinstance(a, float) or isinstance(b, float):
            if _floats_differ(a, b):
                diffs.append(f"{field}: {a} != {b}")
        elif a != b:
            diffs.append(f"{field}: {a} != {b}")

    def normalized(overview: FinancialOverview) -> list[tuple]:
        return sorted(
            (
                (
                    e.category_id,
                    e.category_name,
                    round(e.amount, 2),
                    sorted((s.subcategory_id, s.subcategory_name, round(s.amount, 2)) for s in e.subcategories),
                )
                for e in overview.expenses_by_category
            ),
            key=lambda t: (-t[2], str(t[0])),
        )

    for a_cat, b_cat in zip(normalized(primary), normalized(shadow)):
        if a_cat[0] != b_cat[0] or _floats_differ(a_cat[2], b_cat[2]):
            diffs.append(f"expenses_by_category: {a_cat[:3]} != {b_cat[:3]}")
        elif a_cat[1] != b_cat[1]:
            diffs.append(f"category_name[{a_cat[0]}]: {a_cat[1]!r} != {b_cat[1]!r}")
        else:
            for a_sub, b_sub in zip(a_cat[3], b_cat[3]):
                if a_sub[0] != b_sub[0] or _floats_differ(a_sub[2], b_sub[2]):
                    diffs.append(f"subcategories[{a_cat[0]}]: {a_sub} != {b_sub}")
    if len(primary.expenses_by_category) != len(shadow.expenses_by_category):
        diffs.append(
            f"expenses_by_category.length: {len(primary.expenses_by_category)} != {len(shadow.expenses_by_category)}"
        )
    return diffs


def diff_monthly(primary: list[MonthlyExpenses], shadow: list[MonthlyExpenses]) -> list[str]:
    a_map = {m.month: m.total_expenses for m in primary}
    b_map = {m.month: m.total_expenses for m in shadow}
    diffs = []
    for month in sorted(a_map.keys() | b_map.keys()):
        a, b = a_map.get(month), b_map.get(month)
        if a is None or b is None or _floats_differ(a, b):
            diffs.append(f"month[{month}]: {a} != {b}")
    return diffs


def diff_transactions(
    primary: list[TransactionProjection],
    shadow: list[TransactionProjection],
    limit: int,
) -> list[str]:
    a_ids, b_ids = {t.id for t in primary}, {t.id for t in shadow}
    if a_ids == b_ids:
        return []
    if len(primary) >= limit or len(shadow) >= limit:
        # Ved limit-trunkering er forskellige udsnit forventelige (kendt
        # ordens-divergens); log kun som info-agtig diff.
        return [
            f"transactions(limit-trunkeret): |kun_legacy|={len(a_ids - b_ids)} |kun_analytics|={len(b_ids - a_ids)}"
        ]
    return [f"transactions: kun_legacy={sorted(a_ids - b_ids)} kun_analytics={sorted(b_ids - a_ids)}"]


class DualReadFinancialAnalyticsRepository(IFinancialAnalyticsPort):
    def __init__(self, primary: IFinancialAnalyticsPort, shadow: IFinancialAnalyticsPort) -> None:
        self._primary = primary
        self._shadow = shadow

    def _log_divergence(self, query: str, account_id: int, diffs: list[str]) -> None:
        if diffs:
            # Diffs indgår i selve beskeden — standard log-formatet
            # medtager ikke extra-felter, og divergenser skal kunne
            # læses direkte med `docker logs | grep dual_read`.
            logger.warning(
                "analytics.dual_read.divergence query=%s account_id=%s diff=%s",
                query,
                account_id,
                "; ".join(diffs),
                extra={"query_name": query, "account_id": account_id, "diff": diffs},
            )

    def get_financial_overview(
        self,
        account_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> FinancialOverview:
        result = self._primary.get_financial_overview(account_id, start_date, end_date)
        try:
            shadow = self._shadow.get_financial_overview(account_id, start_date, end_date)
            self._log_divergence("financial_overview", account_id, diff_overviews(result, shadow))
        except Exception:
            logger.warning("analytics.dual_read.shadow_error query=financial_overview", exc_info=True)
        return result

    def get_expenses_by_month(
        self,
        account_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        budget_start_day: int = 1,
    ) -> list[MonthlyExpenses]:
        result = self._primary.get_expenses_by_month(account_id, start_date, end_date, budget_start_day)
        try:
            shadow = self._shadow.get_expenses_by_month(account_id, start_date, end_date, budget_start_day)
            self._log_divergence("expenses_by_month", account_id, diff_monthly(result, shadow))
        except Exception:
            logger.warning("analytics.dual_read.shadow_error query=expenses_by_month", exc_info=True)
        return result

    def list_transactions(
        self,
        account_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        category_id: Optional[int] = None,
        tx_type: Optional[str] = None,
        limit: int = 100,
    ) -> list[TransactionProjection]:
        result = self._primary.list_transactions(account_id, start_date, end_date, category_id, tx_type, limit)
        try:
            shadow = self._shadow.list_transactions(account_id, start_date, end_date, category_id, tx_type, limit)
            self._log_divergence("transactions", account_id, diff_transactions(result, shadow, limit))
        except Exception:
            logger.warning("analytics.dual_read.shadow_error query=transactions", exc_info=True)
        return result
