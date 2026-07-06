from __future__ import annotations

from app.adapters.outbound.elasticsearch.bootstrap import ensure_indices
from app.adapters.outbound.elasticsearch.mappings import (
    INDEX_DEFINITIONS,
    alias_name,
    physical_index,
)
from elasticsearch import AsyncElasticsearch


async def test_ensure_indices_creates_all_aliases(es: AsyncElasticsearch, index_prefix: str) -> None:
    await ensure_indices(es, index_prefix)

    for name in INDEX_DEFINITIONS:
        assert await es.indices.exists_alias(name=alias_name(index_prefix, name))
        assert await es.indices.exists(index=physical_index(index_prefix, name))


async def test_ensure_indices_is_idempotent(es: AsyncElasticsearch, index_prefix: str) -> None:
    await ensure_indices(es, index_prefix)
    await ensure_indices(es, index_prefix)  # må ikke fejle eller duplikere

    for name in INDEX_DEFINITIONS:
        alias = alias_name(index_prefix, name)
        resolved = await es.indices.get_alias(name=alias)
        assert list(resolved.keys()) == [physical_index(index_prefix, name)]


async def test_transactions_mapping_is_strict(es: AsyncElasticsearch, index_prefix: str) -> None:
    await ensure_indices(es, index_prefix)

    mapping = await es.indices.get_mapping(index=alias_name(index_prefix, "transactions"))
    index_mapping = next(iter(mapping.body.values()))["mappings"]
    assert index_mapping["dynamic"] == "strict"
    assert index_mapping["properties"]["description"]["analyzer"] == "danish"
