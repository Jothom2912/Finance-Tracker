"""Standalone worker that runs the account creation consumer.

Usage::

    python -m app.consumers.worker
"""

from __future__ import annotations

import asyncio
import logging

from app.consumers.account_creation_consumer import (
    RABBITMQ_URL,
    AccountCreationConsumer,
    build_session_factory,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    logger.info("Starting account-service consumer worker …")

    session_factory = build_session_factory()
    consumer = AccountCreationConsumer(
        rabbitmq_url=RABBITMQ_URL,
        session_factory=session_factory,
    )

    await consumer.run()


if __name__ == "__main__":
    asyncio.run(main())
