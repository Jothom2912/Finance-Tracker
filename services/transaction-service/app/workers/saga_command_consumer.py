"""Consumer for saga commands directed at transaction-service.

Handles:
- saga.cmd.bulk_import_transactions: bulk import transactions
- saga.cmd.rollback_import: soft-delete previously imported transactions (compensation)
"""
from __future__ import annotations

import asyncio
import json
import logging
from decimal import Decimal

import aio_pika
from aio_pika import ExchangeType
from aio_pika.abc import AbstractIncomingMessage

from app.adapters.outbound.unit_of_work import SQLAlchemyUnitOfWork
from app.application.dto import BulkCreateTransactionDTO, BulkCreateTransactionItemDTO
from app.application.service import TransactionService
from app.config import settings
from app.database import async_session_factory

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s")
logger = logging.getLogger(__name__)

EXCHANGE_NAME = "finans_tracker.events"
QUEUE_NAME = "transaction_service.saga_commands"
ROUTING_KEYS = ["saga.cmd.bulk_import_transactions", "saga.cmd.rollback_import"]
MAX_RETRIES = 3


class TransactionSagaCommandConsumer:
    def __init__(self) -> None:
        self._connection: aio_pika.abc.AbstractRobustConnection | None = None
        self._channel: aio_pika.abc.AbstractChannel | None = None

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

        logger.info("Transaction saga command consumer started, listening on %s", ROUTING_KEYS)
        await asyncio.Future()

    async def _on_message(self, message: AbstractIncomingMessage) -> None:
        body = json.loads(message.body.decode("utf-8"))
        event_type = body.get("event_type", "")
        saga_id = body.get("saga_id", "")
        step_name = body.get("step_name", "")

        try:
            if event_type == "saga.cmd.bulk_import_transactions":
                reply = await self._handle_bulk_import(body)
            elif event_type == "saga.cmd.rollback_import":
                reply = await self._handle_rollback_import(body)
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
                await self._publish_reply(saga_id, step_name, {
                    "success": False,
                    "error_message": str(exc),
                })
                await message.ack()
            else:
                logger.warning("Retrying %s saga=%s (attempt %d)", event_type, saga_id, retry_count + 1, exc_info=True)
                await self._republish(message, retry_count + 1)
                await message.ack()

    async def _handle_bulk_import(self, body: dict) -> dict:
        user_id = body["user_id"]
        account_id = body["account_id"]
        account_name = body["account_name"]
        items_raw = body.get("items", [])

        items = [
            BulkCreateTransactionItemDTO(
                account_id=account_id,
                account_name=account_name,
                amount=Decimal(item["amount"]),
                transaction_type=item["transaction_type"],
                date=item["date"],
                description=item.get("description", ""),
            )
            for item in items_raw
        ]

        dto = BulkCreateTransactionDTO(items=items, skip_duplicates=True)

        async with async_session_factory() as session:
            uow = SQLAlchemyUnitOfWork(session)
            service = TransactionService(uow=uow, categorization_client=None)
            result = await service.bulk_import(user_id=user_id, dto=dto)

        return {
            "success": True,
            "result_data": {
                "imported": result.imported,
                "duplicates_skipped": result.duplicates_skipped,
                "errors": result.errors,
                "imported_ids": result.imported_ids,
            },
        }

    async def _handle_rollback_import(self, body: dict) -> dict:
        user_id = body["user_id"]
        transaction_ids = body.get("transaction_ids", [])

        if not transaction_ids:
            return {"success": True, "is_compensation": True}

        async with async_session_factory() as session:
            uow = SQLAlchemyUnitOfWork(session)
            service = TransactionService(uow=uow, categorization_client=None)
            for tx_id in transaction_ids:
                try:
                    await service.delete_transaction(tx_id, user_id)
                except Exception:
                    logger.warning("Failed to rollback transaction %d", tx_id, exc_info=True)

        logger.info("Rolled back %d transactions for saga compensation (user=%d)", len(transaction_ids), user_id)
        return {"success": True, "is_compensation": True}

    async def _publish_reply(self, saga_id: str, step_name: str, reply_data: dict) -> None:
        if self._channel is None:
            return
        exchange = await self._channel.declare_exchange(EXCHANGE_NAME, ExchangeType.TOPIC, durable=True)

        is_compensation = reply_data.get("is_compensation", False)
        reply_payload = {
            "event_type": f"saga.reply.{step_name}",
            "saga_id": saga_id,
            "step_name": step_name,
            "success": reply_data.get("success", False),
            "error_message": reply_data.get("error_message"),
            "result_data": reply_data.get("result_data"),
            "is_compensation": is_compensation,
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
    consumer = TransactionSagaCommandConsumer()
    await consumer.start()


if __name__ == "__main__":
    asyncio.run(main())
