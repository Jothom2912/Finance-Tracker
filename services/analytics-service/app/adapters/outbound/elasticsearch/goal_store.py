from __future__ import annotations

from datetime import date
from typing import Optional

from elasticsearch import AsyncElasticsearch

from app.adapters.outbound.elasticsearch.guarded_upsert import guarded_full_state_upsert
from app.adapters.outbound.elasticsearch.mappings import GOALS_INDEX, alias_name
from app.application.ports.outbound import IGoalProjectionStore

_DELETE_SCRIPT = """
ctx._source.is_deleted = true;
ctx._source.updated_at = params.event_ts;
"""


class EsGoalProjectionStore(IGoalProjectionStore):
    def __init__(self, es: AsyncElasticsearch, index_prefix: str = "") -> None:
        self._es = es
        self._alias = alias_name(index_prefix, GOALS_INDEX)

    async def upsert(
        self,
        *,
        goal_id: int,
        user_id: int,
        name: Optional[str],
        target_amount: float,
        current_amount: float,
        target_date: Optional[date],
        status: Optional[str],
        is_deleted: bool,
        event_ts: int,
    ) -> None:
        await guarded_full_state_upsert(
            self._es,
            alias=self._alias,
            doc_id=str(goal_id),
            fields={
                "goal_id": goal_id,
                "user_id": user_id,
                "name": name,
                "target_amount": target_amount,
                "current_amount": current_amount,
                "target_date": target_date.isoformat() if target_date else None,
                "status": status,
                "is_deleted": is_deleted,
            },
            event_ts=event_ts,
        )

    async def mark_deleted(self, *, goal_id: int, event_ts: int) -> None:
        await self._es.update(
            index=self._alias,
            id=str(goal_id),
            script={
                "source": _DELETE_SCRIPT,
                "lang": "painless",
                "params": {"event_ts": event_ts},
            },
            upsert={"goal_id": goal_id, "is_deleted": True, "updated_at": event_ts},
            scripted_upsert=True,
            retry_on_conflict=3,
        )
