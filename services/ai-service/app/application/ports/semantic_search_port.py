"""Port interface for semantic transaction search.

`search` is synchronous (blocking I/O) by contract — the dispatcher offloads
it via anyio.to_thread. Returns (items, elapsed_ms); see analytics_port for
why timing is part of the contract.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from app.domain.models import TransactionItem


@runtime_checkable
class ISemanticSearchPort(Protocol):
    def search(
        self,
        query: str,
        *,
        period: str | None = None,
        filters: dict[str, Any] | None = None,
        top_k: int = 10,
    ) -> tuple[list[TransactionItem], float]: ...
