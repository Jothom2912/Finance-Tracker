from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from app import models  # noqa: F401  (register model on Base.metadata)
from app.adapters.outbound.unit_of_work import SQLAlchemyUnitOfWork
from app.database import Base
from app.domain.entities import Notification, NotificationType
from app.models import NotificationModel
from sqlalchemy import update as sa_update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool


@pytest_asyncio.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


def _n(source_key: str, *, user_id: int = 1) -> Notification:
    return Notification(
        user_id=user_id,
        type=NotificationType.GOAL_REACHED,
        title="Mål nået! 🎉",
        body="Du har nået dit sparemål.",
        source_key=source_key,
    )


async def test_add_assigns_id_and_created_at(session: AsyncSession) -> None:
    uow = SQLAlchemyUnitOfWork(session)
    saved = await uow.notifications.add(_n("k1"))
    await uow.commit()
    assert saved.id is not None
    assert saved.created_at is not None
    assert await uow.notifications.source_key_exists("k1") is True
    assert await uow.notifications.source_key_exists("nope") is False


async def test_duplicate_source_key_raises_integrity_error(session: AsyncSession) -> None:
    uow = SQLAlchemyUnitOfWork(session)
    await uow.notifications.add(_n("dup"))
    await uow.commit()
    with pytest.raises(IntegrityError):
        await uow.notifications.add(_n("dup"))
    await uow.rollback()


async def test_list_is_newest_first_and_excludes_dismissed(session: AsyncSession) -> None:
    uow = SQLAlchemyUnitOfWork(session)
    await uow.notifications.add(_n("a"))
    b = await uow.notifications.add(_n("b"))
    # Distinct created_at so ordering is by time, not by same-ms uuid7 tiebreak.
    await session.execute(
        sa_update(NotificationModel)
        .where(NotificationModel.source_key == "a")
        .values(created_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    )
    await session.execute(
        sa_update(NotificationModel)
        .where(NotificationModel.source_key == "b")
        .values(created_at=datetime(2026, 1, 2, tzinfo=timezone.utc))
    )
    await uow.commit()

    listed = await uow.notifications.list_for_user(1)
    assert [n.source_key for n in listed] == ["b", "a"]

    await uow.notifications.dismiss(b.id, 1)
    await uow.commit()
    assert [n.source_key for n in await uow.notifications.list_for_user(1)] == ["a"]


async def test_unread_count_and_mark_read(session: AsyncSession) -> None:
    uow = SQLAlchemyUnitOfWork(session)
    n1 = await uow.notifications.add(_n("a"))
    await uow.notifications.add(_n("b"))
    await uow.commit()
    assert await uow.notifications.unread_count(1) == 2

    assert await uow.notifications.mark_read(n1.id, 1) is True
    await uow.commit()
    assert await uow.notifications.unread_count(1) == 1

    # unread-only listing drops the read one
    assert [n.source_key for n in await uow.notifications.list_for_user(1, unread_only=True)] == ["b"]


async def test_mark_read_is_scoped_to_owner(session: AsyncSession) -> None:
    uow = SQLAlchemyUnitOfWork(session)
    mine = await uow.notifications.add(_n("mine", user_id=1))
    await uow.commit()
    # user 2 cannot mark user 1's notification
    assert await uow.notifications.mark_read(mine.id, 2) is False
    assert await uow.notifications.dismiss(mine.id, 2) is False


async def test_mark_all_read(session: AsyncSession) -> None:
    uow = SQLAlchemyUnitOfWork(session)
    await uow.notifications.add(_n("a"))
    await uow.notifications.add(_n("b"))
    await uow.notifications.add(_n("c", user_id=99))
    await uow.commit()

    moved = await uow.notifications.mark_all_read(1)
    await uow.commit()
    assert moved == 2
    assert await uow.notifications.unread_count(1) == 0
    assert await uow.notifications.unread_count(99) == 1
