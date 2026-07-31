"""P3-59: notification-services 404 på skrivestierne siger nu at den ikke ved hvorfor.

`mark_read` og `dismiss` lægger ejerskabstjekket i `WHERE`-klausulen
(`postgres_notification_repository.py:100-108`, `:128-136`), så `rowcount == 0` dækker tre
tilstande med samme 404 til klienten: rækken findes ikke, den tilhører en anden, eller den
er allerede afvist.

Testene her kører mod en rigtig (sqlite-)DB frem for en mock, netop fordi påstanden er at de
**tre** tilstande alle rammer den samme gren. Med et fake repository ville jeg kun teste min
egen antagelse om hvad `WHERE`-klausulen gør; her fremprovokeres alle tre for at bevise det.

Det bevidste fravalg står i `_log_no_row_matched`s docstring: vi betaler ikke en ekstra
`SELECT` for at skelne dem, og linjen påstår derfor ikke at vide hvilken det var.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
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

MAIN_LOGGER = "app.main"

OWNER_USER_ID = 1
OTHER_USER_ID = 2


def _auth(user_id: int) -> dict[str, str]:
    token = jwt.encode(
        {"user_id": user_id, "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )
    return {"Authorization": f"Bearer {token}"}


def _records(caplog: pytest.LogCaptureFixture, level: int) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.name == MAIN_LOGGER and r.levelno == level]


def _notification(source_key: str, *, user_id: int) -> Notification:
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


async def _seed(session: AsyncSession, *, user_id: int, source_key: str) -> Notification:
    uow = SQLAlchemyUnitOfWork(session)
    created = await uow.notifications.add(_notification(source_key, user_id=user_id))
    await uow.commit()
    return created


class TestThreeStatesOneStatusCode:
    """Alle tre tilstande fremprovokeret mod en rigtig DB — samme 404, samme linje."""

    async def test_unknown_id_logs_the_ambiguity(
        self, ctx: tuple[AsyncClient, AsyncSession], caplog: pytest.LogCaptureFixture
    ) -> None:
        client, _ = ctx
        unknown = uuid4()

        with caplog.at_level(logging.DEBUG):
            response = await client.post(f"/api/v1/notifications/{unknown}/read", headers=_auth(OWNER_USER_ID))

        assert response.status_code == 404
        records = _records(caplog, logging.WARNING)
        assert len(records) == 1
        message = records[0].getMessage()
        assert str(unknown) in message and str(OWNER_USER_ID) in message
        # Linjen skal navngive sin egen upræcished, ikke gætte på én af de tre.
        assert "findes ikke, tilhører en anden, eller er allerede afvist" in message

    async def test_foreign_notification_hits_the_same_branch(
        self, ctx: tuple[AsyncClient, AsyncSession], caplog: pytest.LogCaptureFixture
    ) -> None:
        """Den interessante af de tre — og den der gør linjen værd at have.

        Rækken findes, den er blot en andens. Klienten får samme 404 som for et ukendt id,
        og indtil nu var det ikke muligt at se forskel nogen steder.
        """
        client, session = ctx
        created = await _seed(session, user_id=OWNER_USER_ID, source_key="p359-foreign")

        with caplog.at_level(logging.DEBUG):
            response = await client.post(f"/api/v1/notifications/{created.id}/read", headers=_auth(OTHER_USER_ID))

        assert response.status_code == 404
        records = _records(caplog, logging.WARNING)
        assert len(records) == 1
        assert str(OTHER_USER_ID) in records[0].getMessage()

    async def test_already_dismissed_hits_the_same_branch(
        self, ctx: tuple[AsyncClient, AsyncSession], caplog: pytest.LogCaptureFixture
    ) -> None:
        """Den tredje tilstand — og beviset for at `dismissed_at`-guarden er med i `WHERE`."""
        client, session = ctx
        created = await _seed(session, user_id=OWNER_USER_ID, source_key="p359-dismissed")

        first = await client.delete(f"/api/v1/notifications/{created.id}", headers=_auth(OWNER_USER_ID))
        assert first.status_code == 204

        with caplog.at_level(logging.DEBUG):
            second = await client.delete(f"/api/v1/notifications/{created.id}", headers=_auth(OWNER_USER_ID))

        assert second.status_code == 404
        records = _records(caplog, logging.WARNING)
        assert len(records) == 1
        assert "allerede afvist" in records[0].getMessage()

    async def test_read_and_dismiss_name_their_own_operation(
        self, ctx: tuple[AsyncClient, AsyncSession], caplog: pytest.LogCaptureFixture
    ) -> None:
        """To ruter deler hjælperen, så de skal stadig kunne skelnes i loggen."""
        client, _ = ctx
        unknown = uuid4()

        with caplog.at_level(logging.DEBUG):
            await client.post(f"/api/v1/notifications/{unknown}/read", headers=_auth(OWNER_USER_ID))
            read_message = _records(caplog, logging.WARNING)[0].getMessage()
            caplog.clear()
            await client.delete(f"/api/v1/notifications/{unknown}", headers=_auth(OWNER_USER_ID))
            dismiss_message = _records(caplog, logging.WARNING)[0].getMessage()

        assert "markér-læst" in read_message
        assert "afvisning" in dismiss_message


class TestNegativeControls:
    async def test_successful_mark_read_logs_nothing(
        self, ctx: tuple[AsyncClient, AsyncSession], caplog: pytest.LogCaptureFixture
    ) -> None:
        client, session = ctx
        created = await _seed(session, user_id=OWNER_USER_ID, source_key="p359-ok")

        with caplog.at_level(logging.DEBUG):
            response = await client.post(f"/api/v1/notifications/{created.id}/read", headers=_auth(OWNER_USER_ID))

        assert response.status_code == 204
        assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []

    async def test_remark_read_is_idempotent_and_logs_nothing(
        self, ctx: tuple[AsyncClient, AsyncSession], caplog: pytest.LogCaptureFixture
    ) -> None:
        """Kontrasten til `dismiss`: `mark_read` bruger `coalesce`, så et gen-mark matcher.

        Den er altså **ikke** en af de tre tilstande, og et dobbeltklik i frontenden må ikke
        producere en linje. Var det tilfældet, ville signalet drukne i normal brug.
        """
        client, session = ctx
        created = await _seed(session, user_id=OWNER_USER_ID, source_key="p359-twice")
        assert (
            await client.post(f"/api/v1/notifications/{created.id}/read", headers=_auth(OWNER_USER_ID))
        ).status_code == 204

        with caplog.at_level(logging.DEBUG):
            second = await client.post(f"/api/v1/notifications/{created.id}/read", headers=_auth(OWNER_USER_ID))

        assert second.status_code == 204
        assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []

    async def test_pydantic_422_logs_nothing(
        self, ctx: tuple[AsyncClient, AsyncSession], caplog: pytest.LogCaptureFixture
    ) -> None:
        """Planens negative kontrol nummer to: `limit=0` afvises af Pydantic.

        Admissionsreglen udelukker 422'en eksplicit — den er entydig, og bodyen navngiver
        selv feltet. En linje her ville være starten på en anden access-log.
        """
        client, _ = ctx

        with caplog.at_level(logging.DEBUG):
            response = await client.get("/api/v1/notifications?limit=0", headers=_auth(OWNER_USER_ID))

        assert response.status_code == 422
        assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []

    async def test_mark_all_read_with_nothing_to_do_logs_nothing(
        self, ctx: tuple[AsyncClient, AsyncSession], caplog: pytest.LogCaptureFixture
    ) -> None:
        """`updated=0` er et sandt svar, ikke en afvisning — 200, ingen tvetydighed."""
        client, _ = ctx

        with caplog.at_level(logging.DEBUG):
            response = await client.post("/api/v1/notifications/read-all", headers=_auth(OWNER_USER_ID))

        assert response.status_code == 200
        assert response.json() == {"updated": 0}
        assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []
