"""Sync Unit of Work for account-service.

Wraps a single SQLAlchemy Session, exposing the account repository and
the outbox repository. Both operate on the same session so commit()
is atomic — domain write and outbox insert land in one transaction.
"""

from __future__ import annotations

from typing import Self

from sqlalchemy.orm import Session

from app.adapters.outbound.outbox_repository import SyncOutboxRepository
from app.adapters.outbound.postgresql_account_repository import (
    MySQLAccountRepository as AccountRepository,
)


class SyncUnitOfWork:
    def __init__(self, session: Session) -> None:
        self._session = session
        self.accounts = AccountRepository(session)
        self.outbox = SyncOutboxRepository(session)

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        if exc_type:
            self.rollback()

    def commit(self) -> None:
        self._session.commit()

    def rollback(self) -> None:
        self._session.rollback()
