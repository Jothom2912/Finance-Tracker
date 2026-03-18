from __future__ import annotations

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from app.application.ports.outbound import IEventPublisher
from app.database import Base, get_db
from app.dependencies import get_publisher
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DB_URL, echo=False)
TestSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture()
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture()
def mock_publisher() -> AsyncMock:
    return AsyncMock(spec=IEventPublisher)


@pytest_asyncio.fixture()
async def client(
    db_session: AsyncSession,
    mock_publisher: AsyncMock,
) -> AsyncGenerator[AsyncClient, None]:
    from app.main import app

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    async def _override_get_publisher() -> IEventPublisher:
        return mock_publisher

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_publisher] = _override_get_publisher

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
