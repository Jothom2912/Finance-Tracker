"""Dependency injection wiring for FastAPI.

Critical: ``get_transaction_service`` receives a single ``AsyncSession``
via ``Depends(get_db)`` and passes that **same instance** to both
repositories and the UoW.  This is what makes the Unit of Work pattern
work — ``flush()`` in repositories and ``commit()`` in the service all
operate on the same underlying database transaction.
"""
from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.outbound.postgres_planned_repository import (
    PostgresPlannedTransactionRepository,
)
from app.adapters.outbound.postgres_transaction_repository import (
    PostgresTransactionRepository,
)
from app.adapters.outbound.rabbitmq_publisher import RabbitMQPublisher
from app.adapters.outbound.unit_of_work import SQLAlchemyUnitOfWork
from app.application.ports.inbound import ITransactionService
from app.application.ports.outbound import IEventPublisher
from app.application.service import TransactionService
from app.database import get_db

_publisher: RabbitMQPublisher | None = None


async def get_publisher() -> IEventPublisher:
    assert _publisher is not None, "RabbitMQ publisher not initialised"
    return _publisher


async def get_transaction_service(
    db: AsyncSession = Depends(get_db),
    publisher: IEventPublisher = Depends(get_publisher),
) -> ITransactionService:
    tx_repo = PostgresTransactionRepository(db)
    planned_repo = PostgresPlannedTransactionRepository(db)
    uow = SQLAlchemyUnitOfWork(db)
    return TransactionService(
        transaction_repo=tx_repo,
        planned_repo=planned_repo,
        uow=uow,
        event_publisher=publisher,
    )
