"""Port interface for semantic transaction search."""

from __future__ import annotations

from typing import Any, Protocol

from app.domain.models import TransactionItem


class ISemanticSearchPort(Protocol):
    def search(
        self,
        query: str,
        *,
        period: str | None = None,
        filters: dict[str, Any] | None = None,
        top_k: int = 10,
    ) -> list[TransactionItem]: ...
