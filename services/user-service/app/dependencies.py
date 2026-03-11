from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.outbound.postgres_user_repository import PostgresUserRepository
from app.adapters.outbound.rabbitmq_publisher import RabbitMQPublisher
from app.application.ports.inbound import IUserService
from app.application.ports.outbound import IEventPublisher
from app.application.service import UserService
from app.auth import create_access_token, hash_password, verify_password
from app.database import get_db

_publisher: RabbitMQPublisher | None = None


async def get_publisher() -> IEventPublisher:
    assert _publisher is not None, "RabbitMQ publisher not initialised"
    return _publisher


async def get_user_service(
    db: AsyncSession = Depends(get_db),
    publisher: IEventPublisher = Depends(get_publisher),
) -> IUserService:
    repository = PostgresUserRepository(db)
    return UserService(
        repository=repository,
        event_publisher=publisher,
        hash_password=hash_password,
        verify_password=verify_password,
        create_token=create_access_token,
    )
