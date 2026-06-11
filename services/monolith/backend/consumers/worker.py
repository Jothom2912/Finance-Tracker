"""Standalone worker process that runs all RabbitMQ consumers.

Supports running individual consumers or all of them.

Usage::

    python -m backend.consumers.worker                         # all consumers
    python -m backend.consumers.worker --consumer user-sync
    python -m backend.consumers.worker --consumer category-sync
    python -m backend.consumers.worker --consumer transaction-sync
    python -m backend.consumers.worker --consumer account-sync

Or via uv::

    uv run python -m backend.consumers.worker
"""

from __future__ import annotations

import argparse
import asyncio
import logging

from backend.config import DATABASE_URL, RABBITMQ_URL

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


def _build_session_factory():  # type: ignore[no-untyped-def]
    """Create a sync ``SessionLocal`` factory from the monolith DB url."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


async def _run_user_sync(session_factory: object) -> None:
    """Run only the user-sync consumer."""
    from backend.consumers.user_sync import UserSyncConsumer

    consumer = UserSyncConsumer(
        rabbitmq_url=RABBITMQ_URL,
        db_session_factory=session_factory,
    )
    await consumer.run()


async def _run_category_sync(session_factory: object) -> None:
    """Run only the category-sync consumer."""
    from backend.consumers.category_sync import CategorySyncConsumer

    consumer = CategorySyncConsumer(
        rabbitmq_url=RABBITMQ_URL,
        db_session_factory=session_factory,
    )
    await consumer.run()


async def _run_transaction_sync(session_factory: object) -> None:
    """Run only the transaction-sync consumer."""
    from backend.consumers.transaction_sync import TransactionSyncConsumer

    consumer = TransactionSyncConsumer(
        rabbitmq_url=RABBITMQ_URL,
        db_session_factory=session_factory,
    )
    await consumer.run()


async def _run_account_sync(session_factory: object) -> None:
    """Run only the account-sync consumer."""
    from backend.consumers.account_sync import AccountSyncConsumer

    consumer = AccountSyncConsumer(
        rabbitmq_url=RABBITMQ_URL,
        db_session_factory=session_factory,
    )
    await consumer.run()


async def main(consumer_name: str | None = None) -> None:
    logger.info("Starting consumer worker …")

    session_factory = _build_session_factory()

    if consumer_name == "user-sync":
        logger.info("Running user-sync consumer only")
        await _run_user_sync(session_factory)
    elif consumer_name == "category-sync":
        logger.info("Running category-sync consumer only")
        await _run_category_sync(session_factory)
    elif consumer_name == "transaction-sync":
        logger.info("Running transaction-sync consumer only")
        await _run_transaction_sync(session_factory)
    elif consumer_name == "account-sync":
        logger.info("Running account-sync consumer only")
        await _run_account_sync(session_factory)
    else:
        logger.info("Running all consumers")
        await asyncio.gather(
            _run_user_sync(session_factory),
            _run_category_sync(session_factory),
            _run_transaction_sync(session_factory),
            _run_account_sync(session_factory),
        )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RabbitMQ consumer worker")
    parser.add_argument(
        "--consumer",
        choices=[
            "user-sync",
            "category-sync",
            "transaction-sync",
            "account-sync",
        ],
        default=None,
        help="Run a specific consumer (default: all)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    asyncio.run(main(args.consumer))
