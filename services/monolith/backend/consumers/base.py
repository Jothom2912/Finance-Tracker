from __future__ import annotations

import asyncio
import json
import logging
from abc import ABC, abstractmethod

import aio_pika
from aio_pika import DeliveryMode, ExchangeType, Message
from aio_pika.abc import (
    AbstractChannel,
    AbstractConnection,
    AbstractExchange,
    AbstractIncomingMessage,
    AbstractQueue,
)
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)

HEADER_RETRY_COUNT = "x-retry-count"
_CLEANUP_DAYS = 7


class BaseConsumer(ABC):
    """Reusable async RabbitMQ consumer with retry, DLQ, and idempotency.

    Idempotency is backed by a MySQL ``processed_events`` table keyed
    on ``(correlation_id, consumer_name)``.  This survives process
    restarts, unlike the previous in-memory set.

    Subclasses implement ``handle`` with domain-specific logic.  The base
    class takes care of connection setup, dead-letter routing, retry with
    back-off, and idempotency checks.
    """

    def __init__(
        self,
        rabbitmq_url: str,
        queue_name: str,
        routing_key: str,
        db_session_factory: object,
        exchange_name: str = "finans_tracker.events",
        max_retries: int = 3,
    ) -> None:
        self._url = rabbitmq_url
        self._queue_name = queue_name
        self._routing_key = routing_key
        self._db_session_factory = db_session_factory
        self._exchange_name = exchange_name
        self._max_retries = max_retries

        self._connection: AbstractConnection | None = None
        self._channel: AbstractChannel | None = None
        self._exchange: AbstractExchange | None = None
        self._queue: AbstractQueue | None = None

    # ── connection ──────────────────────────────────────────────────

    async def connect(self) -> None:
        self._connection = await aio_pika.connect_robust(self._url)
        self._channel = await self._connection.channel()

        self._exchange = await self._channel.declare_exchange(
            self._exchange_name,
            ExchangeType.TOPIC,
            durable=True,
        )

        dlx_name = f"{self._exchange_name}.dlx"
        dlx = await self._channel.declare_exchange(
            dlx_name,
            ExchangeType.DIRECT,
            durable=True,
        )

        dlq_name = f"{self._queue_name}.dlq"
        dlq = await self._channel.declare_queue(dlq_name, durable=True)
        await dlq.bind(dlx, routing_key=self._queue_name)

        self._queue = await self._channel.declare_queue(
            self._queue_name,
            durable=True,
            arguments={
                "x-dead-letter-exchange": dlx_name,
                "x-dead-letter-routing-key": self._queue_name,
            },
        )
        await self._queue.bind(self._exchange, routing_key=self._routing_key)

        logger.info(
            "Connected — queue=%s, routing_key=%s, dlq=%s",
            self._queue_name,
            self._routing_key,
            dlq_name,
        )

    # ── idempotency ──────────────────────────────────────────────────

    def _is_already_processed(self, correlation_id: str) -> bool:
        """Check the DB for a previously recorded correlation_id.

        Session is created and closed inside this method so it is safe
        to call via ``asyncio.to_thread``.
        """
        from backend.models.mysql.processed_event import ProcessedEvent

        session = self._db_session_factory()
        try:
            row = (
                session.query(ProcessedEvent)
                .filter(
                    ProcessedEvent.correlation_id == correlation_id,
                    ProcessedEvent.consumer_name == self._queue_name,
                )
                .first()
            )
            return row is not None
        finally:
            session.close()

    def _record_processed(self, correlation_id: str, event_type: str) -> None:
        """Insert a processed-event row.  ``IntegrityError`` on the
        unique constraint is swallowed — it means another instance
        already recorded the same event (race-condition safe).

        Session is created and closed inside this method so it is safe
        to call via ``asyncio.to_thread``.
        """
        from backend.models.mysql.processed_event import ProcessedEvent

        session = self._db_session_factory()
        try:
            session.add(
                ProcessedEvent(
                    correlation_id=correlation_id,
                    consumer_name=self._queue_name,
                    event_type=event_type,
                )
            )
            session.commit()
        except IntegrityError:
            session.rollback()
            logger.debug(
                "Duplicate insert for correlation_id=%s (race-condition safe)",
                correlation_id,
            )
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _cleanup_old_events(self) -> None:
        """Remove processed-event rows older than ``_CLEANUP_DAYS``.

        Called once at startup to prevent unbounded table growth.
        Session is created and closed inside this method.
        """
        from sqlalchemy import text

        session = self._db_session_factory()
        try:
            result = session.execute(
                text(
                    "DELETE FROM processed_events "
                    "WHERE processed_at < NOW() - INTERVAL :days DAY"
                ),
                {"days": _CLEANUP_DAYS},
            )
            session.commit()
            deleted = result.rowcount
            if deleted:
                logger.info(
                    "Cleaned up %d processed_events older than %d days",
                    deleted,
                    _CLEANUP_DAYS,
                )
        except Exception:
            session.rollback()
            logger.warning(
                "processed_events cleanup failed — will retry next restart",
                exc_info=True,
            )
        finally:
            session.close()

    # ── message dispatch ────────────────────────────────────────────

    async def _on_message(self, message: AbstractIncomingMessage) -> None:
        correlation_id: str | None = None
        event_type: str = ""
        try:
            body = json.loads(message.body.decode("utf-8"))
            correlation_id = body.get("correlation_id", "")
            event_type = str(body.get("event_type", ""))

            if correlation_id:
                already = await asyncio.to_thread(
                    self._is_already_processed, correlation_id,
                )
                if already:
                    logger.info(
                        "Skipping duplicate event (correlation_id=%s)",
                        correlation_id,
                    )
                    await message.ack()
                    return

            await self.handle(body)

            if correlation_id:
                await asyncio.to_thread(
                    self._record_processed, correlation_id, event_type,
                )
            await message.ack()

        except Exception:
            retry_count = self._get_retry_count(message)
            cid = correlation_id or "unknown"

            if retry_count < self._max_retries:
                logger.warning(
                    "Handler failed (correlation_id=%s, retry=%d/%d) — republishing",
                    cid,
                    retry_count + 1,
                    self._max_retries,
                    exc_info=True,
                )
                await self._republish(message, retry_count + 1)
                await message.ack()
            else:
                logger.error(
                    "Handler failed after %d retries (correlation_id=%s) — sending to DLQ",
                    self._max_retries,
                    cid,
                    exc_info=True,
                )
                await message.nack(requeue=False)

    # ── retry helpers ───────────────────────────────────────────────

    @staticmethod
    def _get_retry_count(message: AbstractIncomingMessage) -> int:
        headers = message.headers or {}
        return int(headers.get(HEADER_RETRY_COUNT, 0))

    async def _republish(self, original: AbstractIncomingMessage, retry_count: int) -> None:
        assert self._channel is not None
        assert self._exchange is not None

        headers = dict(original.headers or {})
        headers[HEADER_RETRY_COUNT] = retry_count

        msg = Message(
            body=original.body,
            delivery_mode=DeliveryMode.PERSISTENT,
            content_type="application/json",
            headers=headers,
        )
        await self._exchange.publish(msg, routing_key=self._routing_key)

    # ── abstract handler ────────────────────────────────────────────

    @abstractmethod
    async def handle(self, event_data: dict[str, object]) -> None:
        """Process a single deserialized event.  Raise to trigger retry."""

    # ── run loop ────────────────────────────────────────────────────

    async def run(self) -> None:
        await asyncio.to_thread(self._cleanup_old_events)
        await self.connect()
        assert self._channel is not None
        assert self._queue is not None

        await self._channel.set_qos(prefetch_count=1)
        await self._queue.consume(self._on_message)

        logger.info("Consumer %s is running", self._queue_name)
        await asyncio.Future()  # block forever
