"""Embedding-consumer: transaction-events → description_vector i ES (AI-20).

Egen durable queue ``analytics.embeddings`` på ``transaction.*`` med egen
DLQ — adskilt fra projektions-køen, så Ollama-nedetid/latens aldrig kan
stalle kerneprojektionerne (decision 2026-07-13-embed-worker-placement).

Afviger fra projection_consumer på ét punkt: retries republishes DIREKTE
til egen kø (default exchange), ikke til topic-exchangen — en
topic-republish ville fan-oute retry-kopien til alle andre
``transaction.*``-bundne køer (projektioner, budget, goals).

Kør som selvstændig proces::

    python -m app.workers.embedding_consumer
"""

from __future__ import annotations

import asyncio
import json
import logging

import aio_pika
from aio_pika import ExchangeType
from aio_pika.abc import AbstractChannel, AbstractConnection, AbstractIncomingMessage
from contracts.base import BaseEvent
from contracts.events.transaction import (
    TransactionCategorizedEvent,
    TransactionCreatedEvent,
    TransactionUpdatedEvent,
)

from app.adapters.outbound.elasticsearch.bootstrap import ensure_indices
from app.adapters.outbound.elasticsearch.client import create_es_client
from app.adapters.outbound.elasticsearch.transaction_store import (
    EsTransactionProjectionStore,
)
from app.adapters.outbound.ollama_embedder import OllamaEmbedder
from app.application.embedding_projection import EmbeddingProjector, StaleProjectionError
from app.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)

EXCHANGE_NAME = "finans_tracker.events"
QUEUE_NAME = "analytics.embeddings"
ROUTING_KEYS = ["transaction.*"]
MAX_RETRIES = 3
STALE_RETRY_BACKOFF_S = 1.0

# deleted er bevidst udeladt: tombstones filtreres af alle queries, en
# vektor på dem er ligegyldig — eventet ackes som ignoreret.
EVENT_TYPES: dict[str, type[BaseEvent]] = {
    "transaction.created": TransactionCreatedEvent,
    "transaction.updated": TransactionUpdatedEvent,
    "transaction.categorized": TransactionCategorizedEvent,
}


class EmbeddingConsumer:
    def __init__(self, projector: EmbeddingProjector) -> None:
        self._projector = projector
        self._connection: AbstractConnection | None = None
        self._channel: AbstractChannel | None = None

    async def run(self) -> None:
        self._connection = await aio_pika.connect_robust(settings.rabbitmq_url)
        self._channel = await self._connection.channel()
        await self._channel.set_qos(prefetch_count=1)

        exchange = await self._channel.declare_exchange(EXCHANGE_NAME, ExchangeType.TOPIC, durable=True)
        dlx = await self._channel.declare_exchange(f"{EXCHANGE_NAME}.dlx", ExchangeType.DIRECT, durable=True)

        dlq = await self._channel.declare_queue(f"{QUEUE_NAME}.dlq", durable=True)
        await dlq.bind(dlx, routing_key=QUEUE_NAME)

        queue = await self._channel.declare_queue(
            QUEUE_NAME,
            durable=True,
            arguments={
                "x-dead-letter-exchange": f"{EXCHANGE_NAME}.dlx",
                "x-dead-letter-routing-key": QUEUE_NAME,
            },
        )
        for routing_key in ROUTING_KEYS:
            await queue.bind(exchange, routing_key=routing_key)

        await queue.consume(self._on_message)
        logger.info("Consumer %s lytter på %s", QUEUE_NAME, ROUTING_KEYS)

        await asyncio.Future()

    async def _on_message(self, message: AbstractIncomingMessage) -> None:
        try:
            body = json.loads(message.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            logger.error("Ulæselig payload (routing_key=%s) — DLQ", message.routing_key)
            await message.nack(requeue=False)
            return

        event_type = body.get("event_type", message.routing_key or "")
        correlation_id = body.get("correlation_id", "unknown")

        event_cls = EVENT_TYPES.get(event_type)
        if event_cls is None:
            await message.ack()
            return

        try:
            event = event_cls.model_validate(body)
        except Exception:
            logger.error(
                "Ugyldig event-payload for %s (correlation_id=%s) — DLQ",
                event_type,
                correlation_id,
                exc_info=True,
            )
            await message.nack(requeue=False)
            return

        try:
            await self._projector.handle(event)
            await message.ack()
        except Exception as exc:
            retry_count = int(str((message.headers or {}).get("x-retry-count", 0)))
            if retry_count < MAX_RETRIES:
                log = logger.info if isinstance(exc, StaleProjectionError) else logger.warning
                log(
                    "Embedding fejlede for %s (retry=%d/%d, correlation_id=%s): %s — republishes",
                    event_type,
                    retry_count + 1,
                    MAX_RETRIES,
                    correlation_id,
                    exc,
                )
                if isinstance(exc, StaleProjectionError):
                    # Giv projektions-køen tid til at indhente eventet.
                    # Blokerer hele køen (prefetch=1) — acceptabelt: lav
                    # throughput, og senere events er typisk lige så stale.
                    await asyncio.sleep(STALE_RETRY_BACKOFF_S * (retry_count + 1))
                await self._republish(message, retry_count + 1)
                await message.ack()
            else:
                logger.error(
                    "Max retries nået for %s (correlation_id=%s) — DLQ",
                    event_type,
                    correlation_id,
                    exc_info=True,
                )
                await message.nack(requeue=False)

    async def _republish(self, original: AbstractIncomingMessage, retry_count: int) -> None:
        assert self._channel is not None
        headers = dict(original.headers or {})
        headers["x-retry-count"] = retry_count
        msg = aio_pika.Message(
            body=original.body,
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            content_type="application/json",
            headers=headers,
        )
        # Direkte til egen kø — retry må ikke fan-oute via topic-exchangen.
        await self._channel.default_exchange.publish(msg, routing_key=QUEUE_NAME)


async def main() -> None:
    es = create_es_client(settings)
    await ensure_indices(es, settings.es_index_prefix)

    projector = EmbeddingProjector(
        store=EsTransactionProjectionStore(es, settings.es_index_prefix),
        embedder=OllamaEmbedder(settings.ollama_base_url, settings.embedding_model),
    )
    consumer = EmbeddingConsumer(projector)
    try:
        await consumer.run()
    finally:
        await es.close()


if __name__ == "__main__":
    asyncio.run(main())
