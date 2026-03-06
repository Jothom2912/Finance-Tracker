"""
Unit of Work port — manages transaction boundaries.

Wraps an existing session (does NOT create a new one).
The request-scoped session is created by get_db() and
injected via constructor.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class IUnitOfWork(ABC):
    """Manages transaction boundaries.

    Wraps existing session — does NOT create a new one.
    Use as context manager::

        with uow:
            repo.create(data)
            uow.commit()
    """

    @abstractmethod
    def __enter__(self) -> "IUnitOfWork":
        ...

    @abstractmethod
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        ...

    @abstractmethod
    def commit(self) -> None:
        ...

    @abstractmethod
    def rollback(self) -> None:
        ...
