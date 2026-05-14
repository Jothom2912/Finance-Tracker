"""Backfill category_name on transactions by re-emitting categorization events.

Reads existing categorization results from categorization-service's
PostgreSQL, looks up subcategory names, and publishes
TransactionCategorizedEvent for each — the transaction-service's
consumer will update category_name on each transaction.

This is idempotent: the consumer overwrites categorization fields,
so re-running is safe.

Usage::

    # Dry run (default) — show what would be emitted
    uv run python scripts/backfill_category_names.py

    # Actually emit events
    uv run python scripts/backfill_category_names.py --execute

Environment variables::

    CATEGORIZATION_SERVICE_DB_URL   PostgreSQL connection (categorization-service)
    RABBITMQ_URL                    RabbitMQ connection URL
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SERVICE_ROOT = _REPO_ROOT / "services" / "categorization-service"
for candidate in (_SERVICE_ROOT, _REPO_ROOT):
    if candidate.exists() and str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from dotenv import load_dotenv

_ENV_FILE = _REPO_ROOT / ".env"
if _ENV_FILE.exists():
    load_dotenv(_ENV_FILE)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
)
logger = logging.getLogger("backfill-category-names")

CAT_DB_URL = os.getenv(
    "CATEGORIZATION_SERVICE_DB_URL",
    "postgresql://categorization_service:categorization_service_pass@localhost:5435/categorization",
)
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

EXCHANGE_NAME = "finans_tracker.events"


async def _fetch_results_with_names(database_url: str, limit: int | None = None) -> list[dict]:
    """Fetch categorization results joined with subcategory names."""
    import psycopg2

    url = database_url
    for prefix in ("postgresql+asyncpg://", "postgresql+psycopg2://"):
        url = url.replace(prefix, "postgresql://")

    conn = psycopg2.connect(url)
    try:
        with conn.cursor() as cur:
            query = """
                SELECT
                    cr.transaction_id,
                    cr.category_id,
                    cr.subcategory_id,
                    cr.merchant_id,
                    cr.tier,
                    cr.confidence,
                    cr.model_version,
                    COALESCE(sc.name, '') AS subcategory_name
                FROM categorization_results cr
                LEFT JOIN subcategories sc ON sc.id = cr.subcategory_id
                ORDER BY cr.transaction_id
            """
            if limit is not None:
                query += f" LIMIT {int(limit)}"
            cur.execute(query)
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]
    finally:
        conn.close()


async def _publish_events(rabbitmq_url: str, results: list[dict]) -> int:
    import aio_pika
    from aio_pika import DeliveryMode, ExchangeType, Message
    from contracts.events.transaction import TransactionCategorizedEvent

    connection = await aio_pika.connect_robust(rabbitmq_url)
    channel = await connection.channel()
    exchange = await channel.declare_exchange(EXCHANGE_NAME, ExchangeType.TOPIC, durable=True)

    published = 0
    try:
        for row in results:
            event = TransactionCategorizedEvent(
                transaction_id=row["transaction_id"],
                category_id=row["category_id"],
                subcategory_id=row["subcategory_id"],
                subcategory_name=row["subcategory_name"],
                merchant_id=row["merchant_id"],
                tier=row["tier"],
                confidence=row["confidence"],
                model_version=row["model_version"],
            )
            message = Message(
                body=event.to_json().encode("utf-8"),
                delivery_mode=DeliveryMode.PERSISTENT,
                content_type="application/json",
            )
            await exchange.publish(message, routing_key="transaction.categorized")
            published += 1

            if published % 50 == 0:
                logger.info("Published %d / %d events", published, len(results))
    finally:
        await connection.close()

    return published


async def run(database_url: str, rabbitmq_url: str, execute: bool, limit: int | None = None) -> None:
    results = await _fetch_results_with_names(database_url, limit=limit)
    logger.info("Found %d categorization results to backfill", len(results))

    if not results:
        logger.info("Nothing to backfill.")
        return

    with_name = sum(1 for r in results if r["subcategory_name"])
    without_name = len(results) - with_name
    logger.info("  With subcategory name:    %d", with_name)
    logger.info("  Without subcategory name: %d", without_name)

    print("\nSample events (first 5):")
    for row in results[:5]:
        print(f"  tx={row['transaction_id']}  cat={row['category_id']}  "
              f"sub={row['subcategory_id']}  name={row['subcategory_name']!r}  "
              f"tier={row['tier']}")
    print()

    if not execute:
        print("DRY RUN — no events published. Pass --execute to emit.")
        return

    published = await _publish_events(rabbitmq_url, results)
    logger.info("Backfill complete: %d events published", published)
    print(f"\n{published} TransactionCategorizedEvent(s) published.")
    print("The transaction-service consumer will update category_name on each transaction.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Re-emit categorization events with subcategory names to backfill category_name."
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually publish events. Without this flag, only a dry-run report is shown.",
    )
    parser.add_argument(
        "--database-url",
        default=CAT_DB_URL,
        help="Categorization-service PostgreSQL URL",
    )
    parser.add_argument(
        "--rabbitmq-url",
        default=RABBITMQ_URL,
        help="RabbitMQ URL",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only process the first N results (useful for manual verification before full run)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  Backfill category_name via TransactionCategorizedEvent")
    print("=" * 60)
    print()

    asyncio.run(run(args.database_url, args.rabbitmq_url, args.execute, args.limit))


if __name__ == "__main__":
    main()
