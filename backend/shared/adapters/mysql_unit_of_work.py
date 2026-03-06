"""
MySQL adapter for IUnitOfWork.

Wraps an existing SQLAlchemy session — does NOT create one.
Session is injected via constructor.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from backend.shared.ports.unit_of_work import IUnitOfWork


class MySQLUnitOfWork(IUnitOfWork):
    """UoW that wraps an existing SQLAlchemy session."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._committed = False

    def __enter__(self) -> "MySQLUnitOfWork":
        self._committed = False
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        if exc_type is not None:
            self.rollback()
        elif not self._committed:
            self.rollback()

    def commit(self) -> None:
        self._session.commit()
        self._committed = True

    def rollback(self) -> None:
        self._session.rollback()
