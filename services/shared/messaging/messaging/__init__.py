"""finans-tracker-messaging — shared messaging infrastructure.

Transactional outbox (model mixin, repository, publisher worker),
RabbitMQ topic-exchange publisher, and consumer base class with
DLQ + header-based retry.
"""

from __future__ import annotations

from messaging.consumer import (
    ConsumerBase,
    InboxDeduplicator,
    PoisonMessageError,
)
from messaging.logging import setup_worker_logging
from messaging.outbox import (
    OutboxEntry,
    OutboxEventMixin,
    OutboxRepository,
    OutboxStatus,
    compute_backoff,
)
from messaging.rabbitmq import EXCHANGE_NAME, RabbitMQPublisher, SerializableEvent
from messaging.time import utcnow, utcnow_naive
from messaging.worker import OutboxPublisherWorker

__all__ = [
    "EXCHANGE_NAME",
    "ConsumerBase",
    "InboxDeduplicator",
    "OutboxEntry",
    "OutboxEventMixin",
    "OutboxPublisherWorker",
    "OutboxRepository",
    "OutboxStatus",
    "PoisonMessageError",
    "RabbitMQPublisher",
    "SerializableEvent",
    "compute_backoff",
    "setup_worker_logging",
    "utcnow",
    "utcnow_naive",
]
