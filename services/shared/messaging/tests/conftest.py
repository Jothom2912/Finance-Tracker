"""Shared fixtures: an in-memory sqlite outbox table.

NOTE: the SQLite dialect silently drops ``FOR UPDATE SKIP LOCKED``, so
these tests exercise the query predicates/ordering but NOT the row
locking — that path is PostgreSQL-only and covered by the existing
per-service integration tests.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable
from uuid import uuid4

import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import StaticPool

from messaging.outbox import OutboxEventMixin


class Base(DeclarativeBase):
    pass


class OutboxEventModel(OutboxEventMixin, Base):
    pass


class FakeEvent:
    """Minimal SerializableEvent double."""

    def __init__(self, event_type: str = "test.created", **payload: object) -> None:
        self.event_type = event_type
        self.correlation_id = str(uuid4())
        self._payload = payload

    def to_json(self) -> str:
        return json.dumps(
            {
                "event_type": self.event_type,
                "correlation_id": self.correlation_id,
                **self._payload,
            }
        )


@pytest_asyncio.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(
    engine: AsyncEngine,
) -> Callable[[], AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def session(
    session_factory: Callable[[], AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session
