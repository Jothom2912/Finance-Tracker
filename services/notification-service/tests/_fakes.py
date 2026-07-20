"""Shared in-memory fakes for application-layer unit tests."""

from __future__ import annotations

from uuid import uuid4

from app.domain.entities import Notification
from sqlalchemy.exc import IntegrityError


class FakeNotificationRepository:
    def __init__(self) -> None:
        self.rows: list[Notification] = []

    async def source_key_exists(self, source_key: str) -> bool:
        return any(n.source_key == source_key for n in self.rows)

    async def add(self, notification: Notification) -> Notification:
        if await self.source_key_exists(notification.source_key):
            raise IntegrityError("dup", {}, Exception())
        notification.id = uuid4()
        self.rows.append(notification)
        return notification


class FakeUoW:
    def __init__(self) -> None:
        self.notifications = FakeNotificationRepository()
        self.committed = False
        self.rolled_back = False

    async def __aenter__(self) -> "FakeUoW":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type:
            self.rolled_back = True

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


class FakeEmail:
    def __init__(self, *, fail: bool = False) -> None:
        self.sent: list[tuple[int, str]] = []
        self._fail = fail

    async def send(self, *, user_id: int, title: str, body: str) -> None:
        if self._fail:
            raise RuntimeError("smtp down")
        self.sent.append((user_id, title))


class FakeAccountOwner:
    def __init__(self, *, user_id: int | None = None, exc: Exception | None = None) -> None:
        self._user_id = user_id
        self._exc = exc

    async def get_owner_user_id(self, account_id: int) -> int:
        if self._exc is not None:
            raise self._exc
        assert self._user_id is not None
        return self._user_id
