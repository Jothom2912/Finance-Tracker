"""Port interfaces for LLM interactions."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from app.domain.models import ResolvedIntent


class IRouterPort(Protocol):
    async def classify_intent(self, question: str) -> ResolvedIntent: ...


class IResponderPort(Protocol):
    async def stream_response(
        self,
        question: str,
        data_context: str,
    ) -> AsyncIterator[str]: ...
