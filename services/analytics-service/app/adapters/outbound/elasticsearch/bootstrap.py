from __future__ import annotations

import logging

from elasticsearch import AsyncElasticsearch
from elasticsearch import exceptions as es_exceptions

from app.adapters.outbound.elasticsearch.mappings import (
    INDEX_DEFINITIONS,
    alias_name,
    physical_index,
)

logger = logging.getLogger(__name__)


async def ensure_indices(es: AsyncElasticsearch, prefix: str = "") -> None:
    """Idempotent index/alias-bootstrap med versions-migration.

    Kaldes ved opstart af både API-app og workers; den første vinder,
    efterfølgende kald er no-ops. Race mellem to samtidige opstarter
    håndteres ved at sluge already-exists og re-verificere alias-state.

    Peger et alias på en ÆLDRE fysisk version end mappings.INDEX_VERSIONS
    (fx ``transactions_v1`` når koden siger v2), migreres per ADR-0004:
    opret ny fysisk med ny mapping → server-side ``_reindex`` → atomisk
    alias-swap. Den gamle fysiske beholdes som rollback (peg alias
    tilbage manuelt); slet den når den nye version har baket.

    Kendt vindue: writes der lander via alias mellem reindex og swap
    kopieres ikke med. Accepteret — projektionerne er konvergente og
    genopbyggelige (events/backfill indhenter dem).
    """
    for name, definition in INDEX_DEFINITIONS.items():
        alias = alias_name(prefix, name)
        index = physical_index(prefix, name)

        if not await es.indices.exists_alias(name=alias):
            await _create(es, index, definition, alias=alias)
            continue

        current = list((await es.indices.get_alias(name=alias)).keys())
        if index in current:
            continue

        logger.info("Alias %s peger på %s — migrerer til %s", alias, current, index)
        await _create(es, index, definition, alias=None)
        await es.reindex(
            source={"index": alias},
            dest={"index": index},
            wait_for_completion=True,
            refresh=True,
        )
        try:
            await es.indices.update_aliases(
                actions=[
                    *({"remove": {"index": old, "alias": alias}} for old in current),
                    {"add": {"index": index, "alias": alias}},
                ]
            )
        except es_exceptions.ApiError:
            # Parallel bootstrap kan have swappet før os — fejl er kun
            # reel hvis aliaset stadig ikke peger på den nye fysiske.
            after = list((await es.indices.get_alias(name=alias)).keys())
            if index not in after:
                raise
        logger.info("Migrerede %s: %s → %s (gamle indices beholdt til rollback)", alias, current, index)


async def _create(
    es: AsyncElasticsearch,
    index: str,
    definition: dict,
    *,
    alias: str | None,
) -> None:
    try:
        await es.indices.create(
            index=index,
            settings=definition["settings"],
            mappings=definition["mappings"],
            aliases={alias: {}} if alias else None,
        )
        logger.info("Oprettede index %s%s", index, f" med alias {alias}" if alias else "")
    except es_exceptions.BadRequestError as exc:
        if exc.error != "resource_already_exists_exception":
            raise
        logger.info("Index %s fandtes allerede (parallel bootstrap)", index)
