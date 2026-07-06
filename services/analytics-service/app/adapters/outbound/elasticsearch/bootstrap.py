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
    """Idempotent index/alias-bootstrap.

    Kaldes ved opstart af både API-app og consumer-worker; den første
    vinder, efterfølgende kald er no-ops. Race mellem to samtidige
    opstarter håndteres ved at sluge already-exists.
    """
    for name, definition in INDEX_DEFINITIONS.items():
        alias = alias_name(prefix, name)
        index = physical_index(prefix, name)

        if await es.indices.exists_alias(name=alias):
            continue

        try:
            await es.indices.create(
                index=index,
                settings=definition["settings"],
                mappings=definition["mappings"],
                aliases={alias: {}},
            )
            logger.info("Oprettede index %s med alias %s", index, alias)
        except es_exceptions.BadRequestError as exc:
            if exc.error != "resource_already_exists_exception":
                raise
            logger.info("Index %s fandtes allerede (parallel bootstrap)", index)
