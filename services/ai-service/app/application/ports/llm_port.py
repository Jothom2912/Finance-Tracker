"""Port interfaces for LLM interactions.

classify_intent returns (intent, elapsed_ms) — see analytics_port for why
timing is part of the contract. stream_response is an async-generator
function: calling it returns the iterator directly (no awaiting the call).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

from app.domain.models import ResolvedIntent


@runtime_checkable
class IRouterPort(Protocol):
    async def classify_intent(self, question: str) -> tuple[ResolvedIntent, float]: ...


@runtime_checkable
class IResponderPort(Protocol):
    def stream_response(
        self,
        question: str,
        data_context: str,
    ) -> AsyncIterator[str]: ...
