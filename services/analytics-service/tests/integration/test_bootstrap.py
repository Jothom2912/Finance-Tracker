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
    vector = index_mapping["properties"]["description_vector"]
    assert vector["type"] == "dense_vector"
    assert vector["dims"] == 1024
    assert vector["similarity"] == "cosine"


async def test_version_bump_reindexes_and_swaps_alias(es: AsyncElasticsearch, index_prefix: str) -> None:
    """Simulerer et eksisterende deploy på v1: alias skal migreres til v2
    med data intakt, og v1 skal beholdes som rollback."""
    alias = alias_name(index_prefix, "transactions")
    old_index = f"{index_prefix}transactions_v1"

    # v1-mapping uden AI-20-felterne (som den så ud før bumpet).
    v1_mappings = {
        "dynamic": "strict",
        "properties": {
            "transaction_id": {"type": "long"},
            "user_id": {"type": "long"},
            "is_deleted": {"type": "boolean"},
        },
    }
    await es.indices.create(index=old_index, mappings=v1_mappings, aliases={alias: {}})
    await es.index(
        index=alias,
        id="42",
        document={"transaction_id": 42, "user_id": 7, "is_deleted": False},
        refresh=True,
    )

    await ensure_indices(es, index_prefix)

    resolved = await es.indices.get_alias(name=alias)
    assert list(resolved.keys()) == [physical_index(index_prefix, "transactions")]
    doc = await es.get(index=alias, id="42")
    assert doc["_source"]["transaction_id"] == 42
    # Gammel fysisk beholdes til rollback.
    assert await es.indices.exists(index=old_index)

    # Idempotent: endnu et kald må ikke reindexe/fejle.
    await ensure_indices(es, index_prefix)
