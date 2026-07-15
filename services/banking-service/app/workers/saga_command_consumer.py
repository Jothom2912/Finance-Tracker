"""Consumer for saga commands directed at banking-service.

Handles:
- saga.cmd.bank_fetch_transactions: fetch from Enable Banking API
- saga.cmd.mark_sync_complete: update last_synced_at + emit BankSyncCompletedEvent
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from uuid import UUID

import aio_pika
from aio_pika import ExchangeType
from aio_pika.abc import AbstractIncomingMessage
from contracts.events.bank import BankSyncCompletedEvent
from messaging import OutboxRepository
from sqlalchemy import select

from app.adapters.outbound.enable_banking_client import EnableBankingClient, EnableBankingConfig
from app.config import settings
from app.database import async_session_factory
from app.models import BankConnectionModel
from app.models.outbox import OutboxEventModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s")
logger = logging.getLogger(__name__)

EXCHANGE_NAME = "finans_tracker.events"
QUEUE_NAME = "banking_service.saga_commands"
ROUTING_KEYS = ["saga.cmd.bank_fetch_transactions", "saga.cmd.mark_sync_complete"]
MAX_RETRIES = 3


class BankingSagaCommandConsumer:
    def __init__(self) -> None:
        self._connection: aio_pika.abc.AbstractRobustConnection | None = None
        self._channel: aio_pika.abc.AbstractChannel | None = None
        self._banking_client: EnableBankingClient | None = None

    def _get_banking_client(self) -> EnableBankingClient:
        if self._banking_client is None:
            config = EnableBankingConfig(
                app_id=settings.ENABLE_BANKING_APP_ID,
                key_path=settings.ENABLE_BANKING_KEY_PATH,
                redirect_uri=settings.ENABLE_BANKING_REDIRECT_URI,
                max_tx_pages=settings.MAX_TX_PAGES,
            )
            self._banking_client = EnableBankingClient(config)
        return self._banking_client

    async def aclose(self) -> None:
        if self._banking_client is not None:
            await self._banking_client.aclose()
            self._banking_client = None
        if self._connection is not None:
            await self._connection.close()

    async def start(self) -> None:
        self._connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
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
        for key in ROUTING_KEYS:
            await queue.bind(exchange, routing_key=key)
        await queue.consume(self._on_message)

        logger.info("Banking saga command consumer started, listening on %s", ROUTING_KEYS)
        await asyncio.Future()

    async def _on_message(self, message: AbstractIncomingMessage) -> None:
        # Parse inside error handling: a malformed body is dead-lettered
        # instead of crashing the consumer callback.
        try:
            body = json.loads(message.body.decode("utf-8"))
        except Exception:
            logger.error("Invalid JSON on %s — sending to DLQ", QUEUE_NAME, exc_info=True)
            await message.nack(requeue=False)
            return
        event_type = body.get("event_type", "")
        saga_id = body.get("saga_id", "")
        step_name = body.get("step_name", "")

        try:
            if event_type == "saga.cmd.bank_fetch_transactions":
                reply = await self._handle_fetch_transactions(body)
            elif event_type == "saga.cmd.mark_sync_complete":
                reply = await self._handle_mark_sync_complete(body)
            else:
                logger.warning("Unknown saga command: %s", event_type)
                await message.nack(requeue=False)
                return

            await self._publish_reply(saga_id, step_name, reply)
            await message.ack()

        except Exception as exc:
            retry_count = (message.headers or {}).get("x-retry-count", 0)
            if isinstance(retry_count, bytes):
                retry_count = int(retry_count)
            if retry_count >= MAX_RETRIES:
                logger.error("Max retries for %s saga=%s — sending failure reply", event_type, saga_id, exc_info=True)
                await self._publish_reply(
                    saga_id,
                    step_name,
                    {
                        "success": False,
                        "error_message": str(exc),
                    },
                )
                await message.ack()
            else:
                logger.warning("Retrying %s saga=%s (attempt %d)", event_type, saga_id, retry_count + 1, exc_info=True)
                await self._republish(message, retry_count + 1)
                await message.ack()

    async def _handle_fetch_transactions(self, body: dict) -> dict:
        connection_id = body["connection_id"]
        bank_account_uid = body.get("bank_account_uid", "")
        date_from = body.get("date_from")

        # Expiry gate mirrors start_sync_saga (audit H9): the API layer
        # already rejects expired consents, but commands can arrive from
        # other producers / after a delay — fail fast with a clear
        # message instead of an opaque EB error deep in the fetch.
        expired_reply = await self._reject_if_consent_expired(connection_id)
        if expired_reply is not None:
            return expired_reply

        client = self._get_banking_client()
        transactions, parse_skipped = await client.get_transactions(
            account_uid=bank_account_uid,
            date_from=date_from,
        )

        items = []
        errors = 0
        for txn in transactions:
            try:
                tx_type = "income" if txn.amount >= 0 else "expense"
                items.append(
                    {
                        "amount": str(abs(txn.amount)),
                        "transaction_type": tx_type,
                        "date": txn.date.isoformat(),
                        "description": txn.description,
                    }
                )
            except Exception:
                errors += 1
                logger.warning("Failed to prepare transaction for saga", exc_info=True)

        return {
            "success": True,
            "result_data": {
                "items": items,
                "total_fetched": len(transactions),
                "parse_skipped": parse_skipped,
                "errors": errors,
            },
        }

    async def _reject_if_consent_expired(self, connection_id: str) -> dict | None:
        """Return a failure reply if the connection's consent has lapsed."""
        async with async_session_factory() as session:
            result = await session.execute(
                select(BankConnectionModel).where(BankConnectionModel.id == UUID(connection_id))
            )
            conn = result.scalar_one_or_none()
        if conn is None or conn.expires_at is None:
            return None
        now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
        if conn.expires_at > now_naive:
            return None
        logger.warning(
            "Rejecting bank_fetch_transactions: consent for connection %s expired at %s",
            connection_id,
            conn.expires_at.isoformat(),
        )
        return {
            "success": False,
            "error_message": (f"Bank consent expired at {conn.expires_at.isoformat()} — reconsent required"),
        }

    async def _handle_mark_sync_complete(self, body: dict) -> dict:
        connection_id = body["connection_id"]
        user_id = body["user_id"]

        async with async_session_factory() as session:
            result = await session.execute(
                select(BankConnectionModel).where(BankConnectionModel.id == UUID(connection_id))
            )
            conn = result.scalar_one_or_none()
            if conn is not None:
                # Naive UTC per column convention; not domain logic, so a
                # direct timestamp (not injected clock) is acceptable here.
                conn.last_synced_at = datetime.now(timezone.utc).replace(tzinfo=None)

                outbox_repo = OutboxRepository(session, OutboxEventModel)
                event = BankSyncCompletedEvent(
                    connection_id=connection_id,
                    account_id=conn.account_id,
                    user_id=user_id,
                    total_fetched=body.get("total_fetched", 0),
                    new_imported=body.get("new_imported", 0),
                    duplicates_skipped=body.get("duplicates_skipped", 0),
                    errors=body.get("errors", 0),
                )
                await outbox_repo.add(
                    event=event,
                    aggregate_type="bank_connection",
                    aggregate_id=connection_id,
                )
                await session.commit()

        return {"success": True}

    async def _publish_reply(self, saga_id: str, step_name: str, reply_data: dict) -> None:
        if self._channel is None:
            return
        exchange = await self._channel.declare_exchange(EXCHANGE_NAME, ExchangeType.TOPIC, durable=True)

        reply_payload = {
            "event_type": f"saga.reply.{step_name}",
            "saga_id": saga_id,
            "step_name": step_name,
            "success": reply_data.get("success", False),
            "error_message": reply_data.get("error_message"),
            "result_data": reply_data.get("result_data"),
            "is_compensation": False,
        }
        msg = aio_pika.Message(
            body=json.dumps(reply_payload, default=str).encode("utf-8"),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            content_type="application/json",
        )
        await exchange.publish(msg, routing_key=f"saga.reply.{step_name}")

    async def _republish(self, original: AbstractIncomingMessage, retry_count: int) -> None:
        if self._channel is None:
            return
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
    consumer = BankingSagaCommandConsumer()
    try:
        await consumer.start()
    finally:
        await consumer.aclose()


if __name__ == "__main__":
    asyncio.run(main())
