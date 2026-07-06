"""Projection consumer: alle domæne-events → Elasticsearch read-store.

Fire durable køer (én per domæne) bevarer per-producent FIFO, så
timestamp-guards i stores kun skal håndtere cross-domæne/replay-
uorden, ikke intra-domæne race på samme entitet:

- ``analytics.transactions`` ← ``transaction.*``
- ``analytics.accounts``     ← ``account.*``
- ``analytics.taxonomy``     ← ``category.*`` OG ``subcategory.*``
  (topic-gotcha: ``category.*`` matcher ikke subcategory-events)
- ``analytics.goals``        ← ``goal.*``

Robusthed følger goal-services budget_month_closed_consumer: parse-fejl
→ direkte DLQ; handler-fejl → republish med x-retry-count (max 3) → DLQ.
Ingen processed_events-tabel: stores' upserts er konvergente, så
redeliveries er benigne no-ops (ADR-004).

Kør som selvstændig proces::

    python -m app.workers.projection_consumer
"""

from __future__ import annotations

import asyncio
import json
import logging

import aio_pika
from aio_pika import ExchangeType
from aio_pika.abc import AbstractChannel, AbstractConnection, AbstractIncomingMessage

from app.adapters.outbound.elasticsearch.account_store import EsAccountProjectionStore
from app.adapters.outbound.elasticsearch.bootstrap import ensure_indices
from app.adapters.outbound.elasticsearch.client import create_es_client
from app.adapters.outbound.elasticsearch.goal_store import EsGoalProjectionStore
from app.adapters.outbound.elasticsearch.taxonomy_store import EsTaxonomyProjectionStore
from app.adapters.outbound.elasticsearch.transaction_store import (
    EsTransactionProjectionStore,
)
from app.application.projections import (
    AccountProjector,
    GoalProjector,
    Registry,
    TaxonomyProjector,
    TransactionProjector,
    build_registry,
)
from app.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)

EXCHANGE_NAME = "finans_tracker.events"
MAX_RETRIES = 3

QUEUE_BINDINGS: dict[str, list[str]] = {
    "analytics.transactions": ["transaction.*"],
    "analytics.accounts": ["account.*"],
    "analytics.taxonomy": ["category.*", "subcategory.*"],
    "analytics.goals": ["goal.*"],
}


class ProjectionConsumer:
    def __init__(self, registry: Registry) -> None:
        self._registry = registry
        self._connection: AbstractConnection | None = None
        self._channel: AbstractChannel | None = None

    async def run(self) -> None:
        self._connection = await aio_pika.connect_robust(settings.rabbitmq_url)
        self._channel = await self._connection.channel()
        await self._channel.set_qos(prefetch_count=1)

        exchange = await self._channel.declare_exchange(EXCHANGE_NAME, ExchangeType.TOPIC, durable=True)
        dlx = await self._channel.declare_exchange(f"{EXCHANGE_NAME}.dlx", ExchangeType.DIRECT, durable=True)

        for queue_name, routing_keys in QUEUE_BINDINGS.items():
            dlq = await self._channel.declare_queue(f"{queue_name}.dlq", durable=True)
            await dlq.bind(dlx, routing_key=queue_name)

            queue = await self._channel.declare_queue(
                queue_name,
                durable=True,
                arguments={
                    "x-dead-letter-exchange": f"{EXCHANGE_NAME}.dlx",
                    "x-dead-letter-routing-key": queue_name,
                },
            )
            for routing_key in routing_keys:
                await queue.bind(exchange, routing_key=routing_key)

            await queue.consume(self._on_message)
            logger.info("Consumer %s lytter på %s", queue_name, routing_keys)

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

        entry = self._registry.get(event_type)
        if entry is None:
            logger.info(
                "Ignorerer event uden projektion: %s (correlation_id=%s)",
                event_type,
                correlation_id,
            )
            await message.ack()
            return

        event_cls, handler = entry
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
            await handler(event)
            await message.ack()
        except Exception:
            retry_count = int(str((message.headers or {}).get("x-retry-count", 0)))
            if retry_count < MAX_RETRIES:
                logger.warning(
                    "Projektion fejlede for %s (retry=%d/%d, correlation_id=%s) — republishes",
                    event_type,
                    retry_count + 1,
                    MAX_RETRIES,
                    correlation_id,
                    exc_info=True,
                )
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
        exchange = await self._channel.declare_exchange(EXCHANGE_NAME, ExchangeType.TOPIC, durable=True)
        headers = dict(original.headers or {})
        headers["x-retry-count"] = retry_count
        msg = aio_pika.Message(
            body=original.body,
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            content_type="application/json",
            headers=headers,
        )
        await exchange.publish(msg, routing_key=original.routing_key or "")


async def main() -> None:
    es = create_es_client(settings)
    await ensure_indices(es, settings.es_index_prefix)

    prefix = settings.es_index_prefix
    taxonomy_store = EsTaxonomyProjectionStore(es, prefix)
    registry = build_registry(
        transactions=TransactionProjector(EsTransactionProjectionStore(es, prefix), taxonomy_store),
        accounts=AccountProjector(EsAccountProjectionStore(es, prefix)),
        taxonomy=TaxonomyProjector(taxonomy_store),
        goals=GoalProjector(EsGoalProjectionStore(es, prefix)),
    )

    consumer = ProjectionConsumer(registry)
    try:
        await consumer.run()
    finally:
        await es.close()


if __name__ == "__main__":
    asyncio.run(main())
