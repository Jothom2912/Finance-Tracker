from __future__ import annotations

from elasticsearch import AsyncElasticsearch

from app.adapters.outbound.elasticsearch.guarded_upsert import guarded_full_state_upsert
from app.adapters.outbound.elasticsearch.mappings import ACCOUNTS_INDEX, alias_name
from app.application.ports.outbound import IAccountProjectionStore


class EsAccountProjectionStore(IAccountProjectionStore):
    def __init__(self, es: AsyncElasticsearch, index_prefix: str = "") -> None:
        self._es = es
        self._alias = alias_name(index_prefix, ACCOUNTS_INDEX)

    async def upsert(
        self,
        *,
        account_id: int,
        user_id: int,
        name: str,
        saldo: float,
        budget_start_day: int,
        event_ts: int,
    ) -> None:
        await guarded_full_state_upsert(
            self._es,
            alias=self._alias,
            doc_id=str(account_id),
            fields={
                "account_id": account_id,
                "user_id": user_id,
                "name": name,
                "saldo": saldo,
                "budget_start_day": budget_start_day,
            },
            event_ts=event_ts,
        )
