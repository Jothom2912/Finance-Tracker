from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest_asyncio
from app import models  # noqa: F401
from app.adapters.outbound.unit_of_work import SQLAlchemyUnitOfWork
from app.config import settings
from app.database import Base, get_db
from app.domain.entities import Notification, NotificationType
from app.main import app
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool


def _token(user_id: int) -> str:
    return jwt.encode({"user_id": user_id}, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def _auth(user_id: int) -> dict[str, str]:
    return {"Authorization": f"Bearer {_token(user_id)}"}


def _n(source_key: str, *, user_id: int) -> Notification:
    return Notification(
        user_id=user_id,
        type=NotificationType.BANK_SYNC_COMPLETED,
        title="Banksynkronisering færdig",
        body="2 transaktioner blev importeret.",
        source_key=source_key,
    )


@pytest_asyncio.fixture
async def ctx() -> AsyncGenerator[tuple[AsyncClient, AsyncSession], None]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    session = factory()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, session
    app.dependency_overrides.clear()
    await session.close()
    await engine.dispose()


async def _seed(session: AsyncSession) -> list[Notification]:
    uow = SQLAlchemyUnitOfWork(session)
    a = await uow.notifications.add(_n("u1-a", user_id=1))
    b = await uow.notifications.add(_n("u1-b", user_id=1))
    await uow.notifications.add(_n("u2-a", user_id=2))
    await uow.commit()
    return [a, b]


async def test_requires_auth(ctx: tuple[AsyncClient, AsyncSession]) -> None:
    client, _ = ctx
    assert (await client.get("/api/v1/notifications")).status_code == 401


async def test_list_and_unread_count_are_user_scoped(
    ctx: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = ctx
    await _seed(session)

    resp = await client.get("/api/v1/notifications", headers=_auth(1))
    assert resp.status_code == 200
    assert len(resp.json()) == 2

    count = await client.get("/api/v1/notifications/unread-count", headers=_auth(1))
    assert count.json() == {"count": 2}

    # user 2 sees only their own
    assert len((await client.get("/api/v1/notifications", headers=_auth(2))).json()) == 1


async def test_mark_read_flow(ctx: tuple[AsyncClient, AsyncSession]) -> None:
    client, session = ctx
    a, _ = await _seed(session)

    r = await client.post(f"/api/v1/notifications/{a.id}/read", headers=_auth(1))
    assert r.status_code == 204
    assert (await client.get("/api/v1/notifications/unread-count", headers=_auth(1))).json() == {"count": 1}
    # unread-only listing drops the read one
    unread = await client.get("/api/v1/notifications?unread=true", headers=_auth(1))
    assert len(unread.json()) == 1


async def test_mark_read_foreign_notification_is_404(
    ctx: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = ctx
    a, _ = await _seed(session)
    # user 2 cannot mark user 1's notification
    r = await client.post(f"/api/v1/notifications/{a.id}/read", headers=_auth(2))
    assert r.status_code == 404


async def test_read_all(ctx: tuple[AsyncClient, AsyncSession]) -> None:
    client, session = ctx
    await _seed(session)
    r = await client.post("/api/v1/notifications/read-all", headers=_auth(1))
    assert r.json() == {"updated": 2}
    assert (await client.get("/api/v1/notifications/unread-count", headers=_auth(1))).json() == {"count": 0}


async def test_dismiss_removes_from_feed_and_foreign_is_404(
    ctx: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = ctx
    a, b = await _seed(session)

    assert (await client.delete(f"/api/v1/notifications/{a.id}", headers=_auth(2))).status_code == 404
    assert (await client.delete(f"/api/v1/notifications/{a.id}", headers=_auth(1))).status_code == 204

    remaining = await client.get("/api/v1/notifications", headers=_auth(1))
    ids = {r["id"] for r in remaining.json()}
    assert str(a.id) not in ids
    assert str(b.id) in ids
