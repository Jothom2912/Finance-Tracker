from __future__ import annotations

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
