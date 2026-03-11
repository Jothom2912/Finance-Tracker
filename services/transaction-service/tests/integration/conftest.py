from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

TEST_SECRET = "integration-test-secret"
TEST_ALGORITHM = "HS256"

import app.config as _cfg

_cfg.settings.JWT_SECRET = TEST_SECRET  # type: ignore[misc]
_cfg.settings.JWT_ALGORITHM = TEST_ALGORITHM  # type: ignore[misc]

from app.application.ports.outbound import IEventPublisher
from app.database import Base, get_db
from app.dependencies import get_publisher
from app.main import app as fastapi_app

_engine = create_async_engine("sqlite+aiosqlite://", echo=False)
_session_factory = async_sessionmaker(
    _engine, class_=AsyncSession, expire_on_commit=False
)


async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with _session_factory() as session:
        yield session


_mock_publisher = AsyncMock(spec=IEventPublisher)


async def _override_get_publisher() -> IEventPublisher:
    return _mock_publisher


fastapi_app.dependency_overrides[get_db] = _override_get_db
fastapi_app.dependency_overrides[get_publisher] = _override_get_publisher


@pytest_asyncio.fixture(autouse=True)
async def _setup_db():
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    _mock_publisher.reset_mock()


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(
        transport=transport, base_url="http://test"
    ) as ac:
        yield ac


def _make_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    return jwt.encode(payload, TEST_SECRET, algorithm=TEST_ALGORITHM)


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_make_token(1)}"}


@pytest.fixture
def user2_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_make_token(2)}"}


@pytest.fixture
def mock_publisher() -> AsyncMock:
    return _mock_publisher
