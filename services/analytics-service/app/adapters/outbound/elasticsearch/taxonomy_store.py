from __future__ import annotations

from typing import Optional

from elasticsearch import AsyncElasticsearch
from elasticsearch import exceptions as es_exceptions

from app.adapters.outbound.elasticsearch.guarded_upsert import guarded_full_state_upsert
from app.adapters.outbound.elasticsearch.mappings import (
    TAXONOMY_INDEX,
    TRANSACTIONS_INDEX,
    alias_name,
)
from app.application.ports.outbound import ITaxonomyProjectionStore

_RENAME_CATEGORY_SCRIPT = "ctx._source.category_name = params.name;"
_RENAME_SUBCATEGORY_SCRIPT = "ctx._source.subcategory_name = params.name;"


class EsTaxonomyProjectionStore(ITaxonomyProjectionStore):
    def __init__(self, es: AsyncElasticsearch, index_prefix: str = "") -> None:
        self._es = es
        self._alias = alias_name(index_prefix, TAXONOMY_INDEX)
        self._transactions_alias = alias_name(index_prefix, TRANSACTIONS_INDEX)

    async def upsert_category(
        self,
        *,
        category_id: int,
        name: str,
        category_type: str,
        display_order: int,
        is_deleted: bool,
        event_ts: int,
    ) -> bool:
        return await guarded_full_state_upsert(
            self._es,
            alias=self._alias,
            doc_id=f"category:{category_id}",
            fields={
                "doc_type": "category",
                "category_id": category_id,
                "name": name,
                "category_type": category_type,
                "display_order": display_order,
                "is_deleted": is_deleted,
            },
            event_ts=event_ts,
        )

    async def upsert_subcategory(
        self,
        *,
        subcategory_id: int,
        category_id: int,
        name: str,
        is_default: bool,
        is_deleted: bool,
        event_ts: int,
    ) -> bool:
        return await guarded_full_state_upsert(
            self._es,
            alias=self._alias,
            doc_id=f"subcategory:{subcategory_id}",
            fields={
                "doc_type": "subcategory",
                "subcategory_id": subcategory_id,
                "category_id": category_id,
                "name": name,
                "is_default": is_default,
                "is_deleted": is_deleted,
            },
            event_ts=event_ts,
        )

    async def get_subcategory_name(self, subcategory_id: int) -> Optional[str]:
        try:
            doc = await self._es.get(index=self._alias, id=f"subcategory:{subcategory_id}")
        except es_exceptions.NotFoundError:
            return None
        source = doc["_source"]
        if source.get("is_deleted"):
            return None
        name = source.get("name")
        return str(name) if name is not None else None

    async def propagate_category_rename(self, *, category_id: int, name: str) -> None:
        await self._propagate(
            script_source=_RENAME_CATEGORY_SCRIPT,
            field="category_id",
            entity_id=category_id,
            name=name,
        )

    async def propagate_subcategory_rename(self, *, subcategory_id: int, name: str) -> None:
        await self._propagate(
            script_source=_RENAME_SUBCATEGORY_SCRIPT,
            field="subcategory_id",
            entity_id=subcategory_id,
            name=name,
        )

    async def _propagate(self, *, script_source: str, field: str, entity_id: int, name: str) -> None:
        # Refresh først: update_by_query søger, og netop-skrevne
        # transaktionsdokumenter skal med i renamet. Billigt ved disse
        # datamængder; renames er sjældne.
        await self._es.indices.refresh(index=self._transactions_alias)
        await self._es.update_by_query(
            index=self._transactions_alias,
            query={"term": {field: entity_id}},
            script={"source": script_source, "lang": "painless", "params": {"name": name}},
            conflicts="proceed",
        )
