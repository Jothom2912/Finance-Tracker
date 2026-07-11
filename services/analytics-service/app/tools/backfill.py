"""Engangs-backfill af historiske data fra kildeservices til ES.

Kørsel (compose)::

    docker compose run --rm analytics-service \\
        python -m app.tools.backfill --user-id 1

Design (ADR-004):

- **Idempotent & live-safe**: alle skriv går gennem de samme projection
  stores som consumeren, med ``event_ts=0`` — ethvert live event (før
  eller efter backfillen) vinder over backfill-state via stores'
  ``>=``-guards. Genkørsel konvergerer.
- **Taksonomi seedes først** og navne opløses derfra (autoritativ kilde,
  jf. ADR-003) med rækkens denormaliserede navn som fallback — samme
  prioritering som gatewayens overview.
- **Auth**: kortlivet service-JWT per bruger. User-ids angives som
  CLI-args; der findes ingen user-enumeration på tværs af services.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import date
from typing import Any

import httpx
from elasticsearch import AsyncElasticsearch

from app.adapters.outbound.elasticsearch.account_store import EsAccountProjectionStore
from app.adapters.outbound.elasticsearch.bootstrap import ensure_indices
from app.adapters.outbound.elasticsearch.client import create_es_client
from app.adapters.outbound.elasticsearch.goal_store import EsGoalProjectionStore
from app.adapters.outbound.elasticsearch.mappings import INDEX_DEFINITIONS, alias_name
from app.adapters.outbound.elasticsearch.taxonomy_store import EsTaxonomyProjectionStore
from app.adapters.outbound.elasticsearch.transaction_store import (
    EsTransactionProjectionStore,
)
from app.auth import make_service_auth_header
from app.config import Settings, settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(message)s")
logger = logging.getLogger("analytics.backfill")

BACKFILL_EVENT_TS = 0
PAGE_SIZE = 200


class BackfillRunner:
    def __init__(self, es: AsyncElasticsearch, config: Settings) -> None:
        self._es = es
        self._config = config
        prefix = config.es_index_prefix
        self._transactions = EsTransactionProjectionStore(es, prefix)
        self._accounts = EsAccountProjectionStore(es, prefix)
        self._taxonomy = EsTaxonomyProjectionStore(es, prefix)
        self._goals = EsGoalProjectionStore(es, prefix)
        self._category_names: dict[int, str] = {}
        self._subcategory_names: dict[int, str] = {}

    async def run(self, user_ids: list[int]) -> None:
        await ensure_indices(self._es, self._config.es_index_prefix)
        async with httpx.AsyncClient(timeout=30) as http:
            await self._backfill_taxonomy(http, user_ids[0])
            for user_id in user_ids:
                account_ids = await self._backfill_accounts(http, user_id)
                for account_id in account_ids:
                    await self._backfill_transactions(http, user_id, account_id)
                await self._backfill_goals(http, user_id)
        await self._report_counts()

    async def _backfill_taxonomy(self, http: httpx.AsyncClient, user_id: int) -> None:
        headers = make_service_auth_header(user_id, self._config)
        base = self._config.categorization_service_url.rstrip("/")

        categories = (await http.get(f"{base}/api/v1/categories/", headers=headers)).raise_for_status().json()
        for category in categories:
            self._category_names[category["id"]] = category["name"]
            await self._taxonomy.upsert_category(
                category_id=category["id"],
                name=category["name"],
                category_type=category.get("type", ""),
                display_order=category.get("display_order", 0),
                is_deleted=False,
                event_ts=BACKFILL_EVENT_TS,
            )

        subcategories = (await http.get(f"{base}/api/v1/subcategories/", headers=headers)).raise_for_status().json()
        for subcategory in subcategories:
            self._subcategory_names[subcategory["id"]] = subcategory["name"]
            await self._taxonomy.upsert_subcategory(
                subcategory_id=subcategory["id"],
                category_id=subcategory["category_id"],
                name=subcategory["name"],
                is_default=subcategory.get("is_default", True),
                is_deleted=False,
                event_ts=BACKFILL_EVENT_TS,
            )
        logger.info(
            "Taksonomi: %d kategorier, %d subkategorier",
            len(categories),
            len(subcategories),
        )

    async def _backfill_accounts(self, http: httpx.AsyncClient, user_id: int) -> list[int]:
        headers = make_service_auth_header(user_id, self._config)
        base = self._config.account_service_url.rstrip("/")
        accounts = (await http.get(f"{base}/api/v1/accounts/", headers=headers)).raise_for_status().json()

        account_ids: list[int] = []
        for account in accounts:
            account_id = account["idAccount"]
            account_ids.append(account_id)
            await self._accounts.upsert(
                account_id=account_id,
                user_id=account.get("User_idUser") or user_id,
                name=account["name"],
                saldo=float(account.get("saldo", 0)),
                budget_start_day=account.get("budget_start_day", 1),
                event_ts=BACKFILL_EVENT_TS,
            )
        logger.info("Bruger %d: %d konti", user_id, len(accounts))
        return account_ids

    async def _backfill_transactions(self, http: httpx.AsyncClient, user_id: int, account_id: int) -> None:
        base = self._config.transaction_service_url.rstrip("/")
        total = 0
        skip = 0
        while True:
            headers = make_service_auth_header(user_id, self._config)  # frisk token per side
            rows: list[dict[str, Any]] = (
                (
                    await http.get(
                        f"{base}/api/v1/transactions/",
                        params={"account_id": account_id, "skip": skip, "limit": PAGE_SIZE},
                        headers=headers,
                    )
                )
                .raise_for_status()
                .json()
            )
            for row in rows:
                category_id = row.get("category_id")
                subcategory_id = row.get("subcategory_id")
                await self._transactions.upsert_core(
                    transaction_id=row["id"],
                    account_id=row["account_id"],
                    user_id=row.get("user_id") or user_id,
                    amount=float(str(row["amount"])),
                    transaction_type=str(row.get("transaction_type") or "").lower(),
                    tx_date=_parse_date(row["date"]),
                    description=row.get("description") or "",
                    category_id=category_id,
                    category_name=(self._category_names.get(category_id) or row.get("category_name"))
                    if category_id is not None
                    else None,
                    subcategory_id=subcategory_id,
                    subcategory_name=(self._subcategory_names.get(subcategory_id) or row.get("subcategory_name"))
                    if subcategory_id is not None
                    else None,
                    categorization_tier=row.get("categorization_tier"),
                    categorization_confidence=row.get("categorization_confidence"),
                    event_ts=BACKFILL_EVENT_TS,
                )
            total += len(rows)
            if len(rows) < PAGE_SIZE:
                break
            skip += PAGE_SIZE
        logger.info("Konto %d: %d transaktioner", account_id, total)

    async def _backfill_goals(self, http: httpx.AsyncClient, user_id: int) -> None:
        headers = make_service_auth_header(user_id, self._config)
        base = self._config.goal_service_url.rstrip("/")
        goals = (await http.get(f"{base}/api/v1/goals", headers=headers)).raise_for_status().json()

        for goal in goals:
            await self._goals.upsert(
                goal_id=goal["idGoal"],
                user_id=user_id,
                name=goal.get("name"),
                target_amount=float(str(goal["target_amount"])),
                current_amount=float(str(goal["current_amount"])),
                target_date=_parse_date(goal["target_date"]) if goal.get("target_date") else None,
                status=goal.get("status"),
                is_deleted=False,
                event_ts=BACKFILL_EVENT_TS,
            )
        logger.info("Bruger %d: %d mål", user_id, len(goals))

    async def _report_counts(self) -> None:
        prefix = self._config.es_index_prefix
        for name in INDEX_DEFINITIONS:
            alias = alias_name(prefix, name)
            await self._es.indices.refresh(index=alias)
            count = await self._es.count(index=alias)
            logger.info("Index %s: %d dokumenter", alias, count["count"])


def _parse_date(raw: Any) -> date:
    return date.fromisoformat(str(raw)[:10])


async def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill historiske data til analytics-ES")
    parser.add_argument(
        "--user-id",
        type=int,
        action="append",
        required=True,
        dest="user_ids",
        help="Bruger-id der skal backfilles (gentag for flere)",
    )
    args = parser.parse_args()

    es = create_es_client(settings)
    try:
        await BackfillRunner(es, settings).run(args.user_ids)
    finally:
        await es.close()


if __name__ == "__main__":
    asyncio.run(main())
