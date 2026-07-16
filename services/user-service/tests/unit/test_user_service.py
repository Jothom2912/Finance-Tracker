from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.application.dto import LoginDTO, RegisterDTO
from app.application.service import UserService
from app.domain.entities import User, UserWithCredentials
from app.domain.exceptions import (
    InvalidCredentialsException,
    UserAlreadyExistsException,
    UserNotFoundException,
)
from sqlalchemy.exc import IntegrityError

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _make_uow() -> MagicMock:
    """Build a mock UoW whose repos are AsyncMocks."""
    uow = MagicMock()
    uow.users = AsyncMock()
    uow.outbox = AsyncMock()
    uow.commit = AsyncMock()
    uow.rollback = AsyncMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=False)
    return uow


@pytest.fixture()
def uow() -> MagicMock:
    return _make_uow()


@pytest.fixture()
def service(uow: MagicMock) -> UserService:
    return UserService(
        uow=uow,
        hash_password=lambda pw: f"hashed_{pw}",
        verify_password=lambda plain, hashed: hashed == f"hashed_{plain}",
        create_token=lambda uid, uname, email: f"token_{uid}",
    )


def _make_user_with_creds(
    user_id: int = 1,
    username: str = "alice",
    email: str = "alice@example.com",
) -> UserWithCredentials:
    return UserWithCredentials(
        id=user_id,
        username=username,
        email=email,
        password_hash="hashed_secret123",
        created_at=NOW,
    )


def _make_user(
    user_id: int = 1,
    username: str = "alice",
    email: str = "alice@example.com",
) -> User:
    return User(id=user_id, username=username, email=email, created_at=NOW)


# ── register ────────────────────────────────────────────────────────


class TestRegister:
    @pytest.mark.asyncio()
    async def test_register_success(self, service: UserService, uow: MagicMock) -> None:
        uow.users.find_by_email.return_value = None
        uow.users.find_by_username.return_value = None
        uow.users.create.return_value = _make_user_with_creds()

        dto = RegisterDTO(username="alice", email="alice@example.com", password="secret123")
        result = await service.register(dto)

        assert result.id == 1
        assert result.username == "alice"
        assert result.email == "alice@example.com"
        uow.users.create.assert_awaited_once_with(
            username="alice",
            email="alice@example.com",
            password_hash="hashed_secret123",
        )

    @pytest.mark.asyncio()
    async def test_register_writes_outbox_event(self, service: UserService, uow: MagicMock) -> None:
        uow.users.find_by_email.return_value = None
        uow.users.find_by_username.return_value = None
        uow.users.create.return_value = _make_user_with_creds(user_id=42, username="zara", email="zara@example.com")

        dto = RegisterDTO(username="zara", email="zara@example.com", password="secret123")
        await service.register(dto)

        uow.outbox.add.assert_awaited_once()
        call_kwargs = uow.outbox.add.call_args[1]
        event = call_kwargs["event"]
        assert event.event_type == "user.created"
        assert event.user_id == 42
        assert event.email == "zara@example.com"
        assert event.username == "zara"
        assert call_kwargs["aggregate_type"] == "user"
        assert call_kwargs["aggregate_id"] == "42"

    @pytest.mark.asyncio()
    async def test_register_commits_uow(self, service: UserService, uow: MagicMock) -> None:
        uow.users.find_by_email.return_value = None
        uow.users.find_by_username.return_value = None
        uow.users.create.return_value = _make_user_with_creds()

        dto = RegisterDTO(username="alice", email="alice@example.com", password="secret123")
        await service.register(dto)

        uow.commit.assert_awaited_once()

    @pytest.mark.asyncio()
    async def test_register_duplicate_email(self, service: UserService, uow: MagicMock) -> None:
        uow.users.find_by_email.return_value = _make_user_with_creds()

        dto = RegisterDTO(username="bob", email="alice@example.com", password="secret123")

        with pytest.raises(UserAlreadyExistsException):
            await service.register(dto)

        uow.outbox.add.assert_not_awaited()

    @pytest.mark.asyncio()
    async def test_register_duplicate_username(self, service: UserService, uow: MagicMock) -> None:
        uow.users.find_by_email.return_value = None
        uow.users.find_by_username.return_value = _make_user_with_creds()

        dto = RegisterDTO(username="alice", email="new@example.com", password="secret123")

        with pytest.raises(UserAlreadyExistsException):
            await service.register(dto)

        uow.outbox.add.assert_not_awaited()

    @pytest.mark.asyncio()
    async def test_register_concurrent_duplicate_email_raises_conflict(
        self, service: UserService, uow: MagicMock
    ) -> None:
        """Register race (finding 2): a concurrent registration can slip
        past the check-then-insert pre-checks and only get caught by the
        DB's unique constraint on insert. That must surface as the
        existing 409-mapped UserAlreadyExistsException, not an unhandled
        IntegrityError (500).
        """
        uow.users.find_by_email.return_value = None
        uow.users.find_by_username.return_value = None
        uow.users.create.side_effect = IntegrityError(
            "INSERT INTO users ...",
            {},
            Exception('duplicate key value violates unique constraint "ix_users_email"'),
        )

        dto = RegisterDTO(username="dave", email="dave@example.com", password="secret123")

        with pytest.raises(UserAlreadyExistsException) as exc_info:
            await service.register(dto)

        assert exc_info.value.field == "email"
        uow.outbox.add.assert_not_awaited()
        uow.commit.assert_not_awaited()

    @pytest.mark.asyncio()
    async def test_register_concurrent_duplicate_username_raises_conflict(
        self, service: UserService, uow: MagicMock
    ) -> None:
        uow.users.find_by_email.return_value = None
        uow.users.find_by_username.return_value = None
        uow.users.create.side_effect = IntegrityError(
            "INSERT INTO users ...",
            {},
            Exception("UNIQUE constraint failed: users.username"),
        )

        dto = RegisterDTO(username="erin", email="erin@example.com", password="secret123")

        with pytest.raises(UserAlreadyExistsException) as exc_info:
            await service.register(dto)

        assert exc_info.value.field == "username"
        uow.outbox.add.assert_not_awaited()
        uow.commit.assert_not_awaited()

    @pytest.mark.asyncio()
    async def test_register_offloads_password_hashing_from_event_loop(self, uow: MagicMock) -> None:
        """Regression test for finding 1 (H1): bcrypt hashing must be
        offloaded to a worker thread so it doesn't block the event loop.
        A slow synchronous ``hash_password`` should not prevent other
        coroutines (here, a ticker awaiting ``asyncio.sleep``) from
        making progress while it runs.
        """
        uow.users.find_by_email.return_value = None
        uow.users.find_by_username.return_value = None
        uow.users.create.return_value = _make_user_with_creds(user_id=99, username="carol", email="carol@example.com")

        def slow_hash(password: str) -> str:
            time.sleep(0.2)
            return f"hashed_{password}"

        service = UserService(
            uow=uow,
            hash_password=slow_hash,
            verify_password=lambda plain, hashed: hashed == f"hashed_{plain}",
            create_token=lambda uid, uname, email: f"token_{uid}",
        )

        tick_count = 0

        async def ticker() -> None:
            nonlocal tick_count
            while True:
                await asyncio.sleep(0.01)
                tick_count += 1

        dto = RegisterDTO(username="carol", email="carol@example.com", password="secret123")
        ticker_task = asyncio.create_task(ticker())
        try:
            result = await service.register(dto)
        finally:
            ticker_task.cancel()

        # Behavior parity: the result is unaffected by the offload.
        assert result.id == 99
        assert result.username == "carol"

        # If slow_hash had blocked the event loop synchronously for
        # ~0.2s, the ticker (waking every 10ms) would get almost no
        # chance to run. Offloading via anyio.to_thread.run_sync lets
        # the loop keep servicing it while hashing runs in a thread.
        assert tick_count >= 5


# ── login ────────────────────────────────────────────────────────────


class TestLogin:
    @pytest.mark.asyncio()
    async def test_login_success_with_email(self, service: UserService, uow: MagicMock) -> None:
        uow.users.find_by_email.return_value = _make_user_with_creds()

        dto = LoginDTO(username_or_email="alice@example.com", password="secret123")
        result = await service.login(dto)

        assert result.access_token == "token_1"
        assert result.token_type == "bearer"
        assert result.user_id == 1
        assert result.username == "alice"

    @pytest.mark.asyncio()
    async def test_login_success_with_username(self, service: UserService, uow: MagicMock) -> None:
        uow.users.find_by_username.return_value = _make_user_with_creds()

        dto = LoginDTO(username_or_email="alice", password="secret123")
        result = await service.login(dto)

        assert result.access_token == "token_1"
        assert result.user_id == 1

    @pytest.mark.asyncio()
    async def test_login_wrong_password(self, service: UserService, uow: MagicMock) -> None:
        uow.users.find_by_email.return_value = _make_user_with_creds()

        dto = LoginDTO(
            username_or_email="alice@example.com",
            password="wrong_password",
        )

        with pytest.raises(InvalidCredentialsException):
            await service.login(dto)

    @pytest.mark.asyncio()
    async def test_login_user_not_found(self, service: UserService, uow: MagicMock) -> None:
        uow.users.find_by_email.return_value = None

        dto = LoginDTO(username_or_email="nobody@example.com", password="secret123")

        with pytest.raises(InvalidCredentialsException):
            await service.login(dto)

    @pytest.mark.asyncio()
    async def test_login_offloads_password_verification_from_event_loop(self, uow: MagicMock) -> None:
        """Regression test for finding 1 (H1): bcrypt verification must
        be offloaded to a worker thread. See the analogous register()
        test above for the rationale of the ticker-based assertion.
        """
        uow.users.find_by_email.return_value = _make_user_with_creds()

        def slow_verify(plain: str, hashed: str) -> bool:
            time.sleep(0.2)
            return hashed == f"hashed_{plain}"

        service = UserService(
            uow=uow,
            hash_password=lambda pw: f"hashed_{pw}",
            verify_password=slow_verify,
            create_token=lambda uid, uname, email: f"token_{uid}",
        )

        tick_count = 0

        async def ticker() -> None:
            nonlocal tick_count
            while True:
                await asyncio.sleep(0.01)
                tick_count += 1

        dto = LoginDTO(username_or_email="alice@example.com", password="secret123")
        ticker_task = asyncio.create_task(ticker())
        try:
            result = await service.login(dto)
        finally:
            ticker_task.cancel()

        # Behavior parity: the result is unaffected by the offload.
        assert result.access_token == "token_1"
        assert result.user_id == 1

        assert tick_count >= 5


# ── get_user ─────────────────────────────────────────────────────────


class TestGetUser:
    @pytest.mark.asyncio()
    async def test_get_user_success(self, service: UserService, uow: MagicMock) -> None:
        uow.users.find_by_id.return_value = _make_user()

        result = await service.get_user(1)

        assert result.id == 1
        assert result.username == "alice"
        assert result.email == "alice@example.com"

    @pytest.mark.asyncio()
    async def test_get_user_not_found(self, service: UserService, uow: MagicMock) -> None:
        uow.users.find_by_id.return_value = None

        with pytest.raises(UserNotFoundException):
            await service.get_user(999)
