"""Backfill monolith MySQL transaction projection from transaction-service.

Reads every row from transaction-service's PostgreSQL ``transactions``
table and publishes a synthetic ``TransactionCreatedEvent`` per row
directly to the RabbitMQ topic exchange.  The ``TransactionSyncConsumer``
picks these up and upserts into the monolith MySQL ``Transaction``
table, giving analytics/dashboard access to historical data.

This is idempotent — re-running the script is safe because the
consumer treats replays as upserts.

Usage (inside the compose network)::

    docker compose run --rm transaction-service \\
        python /app/scripts/backfill_transaction_projection.py

Or locally with env vars set::

    uv run python scripts/backfill_transaction_projection.py

Environment variables:
    DATABASE_URL       transaction-service PostgreSQL URL
    RABBITMQ_URL       RabbitMQ connection URL
    BACKFILL_BATCH_SIZE  (optional) default 500
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from decimal import Decimal
from pathlib import Path

# Allow running both from repo root and from transaction-service container
_REPO_ROOT = Path(__file__).resolve().parent.parent
_SERVICE_ROOT = _REPO_ROOT / "services" / "transaction-service"
for candidate in (_SERVICE_ROOT, _REPO_ROOT):
    if candidate.exists() and str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import aio_pika  # noqa: E402
from aio_pika import DeliveryMode, ExchangeType, Message  # noqa: E402
from contracts.events.transaction import TransactionCreatedEvent  # noqa: E402
from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from app.models import TransactionModel  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
)
logger = logging.getLogger("backfill")

EXCHANGE_NAME = "finans_tracker.events"


async def _publish_batch(
    exchange: aio_pika.abc.AbstractExchange,
    rows: list[TransactionModel],
) -> int:
    published = 0
    for row in rows:
        event = TransactionCreatedEvent(
            transaction_id=row.id,
            account_id=row.account_id,
            user_id=row.user_id,
            amount=str(row.amount if isinstance(row.amount, Decimal) else Decimal(str(row.amount))),
            transaction_type=row.transaction_type,
            tx_date=row.date,
            category_id=row.category_id,
            category=row.category_name or "",
            description=row.description or "",
            account_name=row.account_name or "",
        )
        message = Message(
            body=event.to_json().encode("utf-8"),
            delivery_mode=DeliveryMode.PERSISTENT,
            content_type="application/json",
        )
        await exchange.publish(message, routing_key=event.event_type)
        published += 1
    return published


async def backfill(database_url: str, rabbitmq_url: str, batch_size: int) -> int:
    """Publish ``transaction.created`` for every row in PostgreSQL.

    Returns the total number of events published.
    """
    engine = create_async_engine(database_url, echo=False)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    connection = await aio_pika.connect_robust(rabbitmq_url)
    channel = await connection.channel()
    exchange = await channel.declare_exchange(EXCHANGE_NAME, ExchangeType.TOPIC, durable=True)

    total = 0
    try:
        async with session_maker() as session:
            offset = 0
            while True:
                stmt = (
                    select(TransactionModel)
                    .order_by(TransactionModel.id)
                    .offset(offset)
                    .limit(batch_size)
                )
                result = await session.execute(stmt)
                rows = list(result.scalars().all())
                if not rows:
                    break

                published = await _publish_batch(exchange, rows)
                total += published
                offset += len(rows)
                logger.info("Published %d events (running total: %d)", published, total)
    finally:
        await connection.close()
        await engine.dispose()

    logger.info("Backfill finished: %d events published", total)
    return total


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Publish synthetic transaction.created events "
        "for every row in transaction-service",
    )
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL"),
        help="PostgreSQL URL (defaults to $DATABASE_URL)",
    )
    parser.add_argument(
        "--rabbitmq-url",
        default=os.environ.get("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/"),
        help="RabbitMQ URL (defaults to $RABBITMQ_URL)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=int(os.environ.get("BACKFILL_BATCH_SIZE", "500")),
        help="Rows fetched per DB query (default: 500)",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if not args.database_url:
        raise SystemExit("DATABASE_URL is required (pass --database-url or set env var)")

    asyncio.run(
        backfill(
            database_url=args.database_url,
            rabbitmq_url=args.rabbitmq_url,
            batch_size=args.batch_size,
        )
    )


if __name__ == "__main__":
    main()
