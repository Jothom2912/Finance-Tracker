"""Embedding-projektor: transaction-events → description_vector (AI-20).

Bevidst state-læsende, ikke payload-læsende: handleren læser dokumentets
fulde state fra read-storen og embedder DEN — én kodesti for alle
transaction-eventtyper (created/updated/categorized), og prosaen får
altid merged state (fx kategorinavn fra categorized + beskrivelse fra
created) uanset event-orden.

Konsekvens: embed-køen kan overhale projektions-køen (samme events, to
uafhængige køer). Er dokumentet endnu ikke projiceret — eller ældre end
eventet — kastes StaleProjectionError, som workeren mapper til
republish/retry (samme mønster som projection_consumer). Stragglers
fanges af backfill_embeddings-værktøjet.

Guard-timestamp er dokumentets ``updated_at`` (state-afledt), ikke
eventets — så konkurrerende re-embeds konvergerer mod nyeste state.
"""

from __future__ import annotations

import logging

from contracts.base import BaseEvent

from app.application.embedding_text import build_embedding_text
from app.application.ports.outbound import IEmbeddingModelPort, IEmbeddingStore
from app.application.projections import event_ts_millis

logger = logging.getLogger(__name__)


class StaleProjectionError(Exception):
    """Dokumentet afspejler endnu ikke eventet — retryable."""


class EmbeddingProjector:
    def __init__(self, store: IEmbeddingStore, embedder: IEmbeddingModelPort) -> None:
        self._store = store
        self._embedder = embedder

    async def handle(self, event: BaseEvent) -> None:
        transaction_id: int = event.transaction_id  # type: ignore[attr-defined]
        event_ts = event_ts_millis(event)

        source = await self._store.get_projection(transaction_id=transaction_id)
        if source is None:
            raise StaleProjectionError(f"transaction {transaction_id} ikke projiceret endnu")
        if source.get("is_deleted"):
            return
        updated_at = int(source.get("updated_at") or 0)
        if updated_at < event_ts:
            raise StaleProjectionError(
                f"transaction {transaction_id}: dokument-updated_at {updated_at} < event_ts {event_ts}"
            )

        vector = await self._embedder.embed(build_embedding_text(source))
        await self._store.update_embedding(
            transaction_id=transaction_id,
            vector=vector,
            event_ts=updated_at,
        )
