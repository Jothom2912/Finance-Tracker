"""Engangs-backfill af description_vector på eksisterende ES-dokumenter (AI-20).

Kørsel (compose)::

    docker compose run --rm analytics-service \\
        python -m app.tools.backfill_embeddings [--user-id N] [--re-embed]

Default embeddes kun dokumenter UDEN vektor (idempotent genkørsel; DLQ-
stragglers fra embedding-consumeren fanges her). ``--re-embed`` tvinger
alle — brug ved skift af embedding-model (husk mapping-dims!).

Live-safe: skriver via samme guardede update som consumeren med
``event_ts = dokumentets updated_at`` — et live event der re-embedder
nyere state vinder altid over backfillen.

NB: bge-m3 via Ollama er langsom (~0.4 s/dokument) — kør per bruger og
off-peak, jf. plan 2026-07-12-ai-service-es-chat §Risks.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from typing import Any

from app.adapters.outbound.elasticsearch.client import create_es_client
from app.adapters.outbound.elasticsearch.mappings import TRANSACTIONS_INDEX, alias_name
from app.adapters.outbound.elasticsearch.transaction_store import (
    EsTransactionProjectionStore,
)
from app.adapters.outbound.ollama_embedder import OllamaEmbedder
from app.application.embedding_text import build_embedding_text
from app.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(message)s")
logger = logging.getLogger("analytics.backfill_embeddings")

PAGE_SIZE = 100


async def run(user_ids: list[int] | None, re_embed: bool) -> None:
    es = create_es_client(settings)
    store = EsTransactionProjectionStore(es, settings.es_index_prefix)
    embedder = OllamaEmbedder(settings.ollama_base_url, settings.embedding_model)
    tx_alias = alias_name(settings.es_index_prefix, TRANSACTIONS_INDEX)

    filters: list[dict[str, Any]] = [{"term": {"is_deleted": False}}]
    if user_ids:
        filters.append({"terms": {"user_id": user_ids}})
    if not re_embed:
        filters.append({"bool": {"must_not": [{"exists": {"field": "description_vector"}}]}})

    done = 0
    try:
        search_after: list[Any] | None = None
        while True:
            response = await es.search(
                index=tx_alias,
                query={"bool": {"filter": filters}},
                sort=[{"transaction_id": {"order": "asc"}}],
                size=PAGE_SIZE,
                search_after=search_after,
                source_excludes=["description_vector"],
            )
            hits = response["hits"]["hits"]
            if not hits:
                break
            for hit in hits:
                source = hit["_source"]
                vector = await embedder.embed(build_embedding_text(source))
                await store.update_embedding(
                    transaction_id=int(source["transaction_id"]),
                    vector=vector,
                    event_ts=int(source.get("updated_at") or 0),
                )
                done += 1
                if done % 50 == 0:
                    logger.info("%d dokumenter embeddet …", done)
            search_after = hits[-1]["sort"]
        await es.indices.refresh(index=tx_alias)
        logger.info("Færdig: %d dokumenter embeddet", done)
    finally:
        await es.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill embeddings på analytics-ES")
    parser.add_argument(
        "--user-id",
        type=int,
        action="append",
        dest="user_ids",
        help="Begræns til bruger-id (gentag for flere; udelad for alle)",
    )
    parser.add_argument(
        "--re-embed",
        action="store_true",
        help="Embed også dokumenter der allerede har en vektor",
    )
    args = parser.parse_args()
    asyncio.run(run(args.user_ids, args.re_embed))


if __name__ == "__main__":
    main()
