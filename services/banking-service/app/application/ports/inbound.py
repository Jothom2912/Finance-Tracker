from __future__ import annotations

from typing import Any, Optional, Protocol
from uuid import UUID


class IBankingService(Protocol):
    async def list_banks(self, country: str = "DK") -> list[dict[str, Any]]: ...

    async def start_connect(
        self, bank_name: str, country: str, account_id: int, user_id: int,
    ) -> dict[str, str]: ...

    async def complete_connect(
        self, auth_code: str, account_id: int, user_id: int,
    ) -> list[dict[str, Any]]: ...

    async def list_connections(self, account_id: int, user_id: int) -> list[dict[str, Any]]: ...

    async def start_sync_saga(
        self, connection_id: UUID, user_id: int, date_from: Optional[str] = None,
    ) -> str: ...

    async def disconnect(self, connection_id: UUID, user_id: int) -> bool: ...
