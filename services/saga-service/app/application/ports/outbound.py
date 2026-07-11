from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from app.domain.entities import SagaInstance


class ISagaRepository(ABC):
    @abstractmethod
    async def save(self, saga: SagaInstance) -> None: ...

    @abstractmethod
    async def get_by_id(self, saga_id: str, *, for_update: bool = False) -> SagaInstance | None:
        """Load a saga by id.

        With ``for_update=True`` the saga row is locked (``SELECT ... FOR UPDATE``)
        for the remainder of the current transaction, serializing concurrent
        read-modify-write flows (reply handling vs. timeout marking).
        """
        ...

    @abstractmethod
    async def get_by_correlation_id(self, correlation_id: str) -> SagaInstance | None: ...

    @abstractmethod
    async def find_stale_ids(self, older_than: datetime) -> list[str]:
        """Cheap staleness scan: ids of active sagas not updated since ``older_than``.

        Returns ids only — callers must re-load each saga under a row lock and
        re-validate before acting, since the scan itself takes no locks.
        """
        ...

    @abstractmethod
    async def update(self, saga: SagaInstance) -> None: ...


class IOutboxRepository(ABC):
    @abstractmethod
    async def add(
        self,
        event_type: str,
        payload_json: str,
        aggregate_type: str,
        aggregate_id: str,
        correlation_id: str | None = None,
    ) -> None: ...


class IUnitOfWork(ABC):
    sagas: ISagaRepository
    outbox: IOutboxRepository

    @abstractmethod
    async def __aenter__(self) -> "IUnitOfWork": ...

    @abstractmethod
    async def __aexit__(self, exc_type: type | None, exc_val: BaseException | None, exc_tb: object) -> None: ...

    @abstractmethod
    async def commit(self) -> None: ...
