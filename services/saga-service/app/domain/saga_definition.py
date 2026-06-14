from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class StepDefinition:
    """Blueprint for a single saga step."""

    name: str
    command_event_type: str
    compensate_event_type: str | None = None


class SagaDefinition(ABC):
    """Protocol defining the structure and behavior of a specific saga type."""

    @property
    @abstractmethod
    def saga_type(self) -> str: ...

    @property
    @abstractmethod
    def steps(self) -> list[StepDefinition]: ...

    @abstractmethod
    def build_command(self, step_index: int, context: dict[str, Any]) -> dict[str, Any]:
        """Build the command payload for a given step using saga context."""
        ...

    @abstractmethod
    def build_compensate_command(self, step_index: int, context: dict[str, Any]) -> dict[str, Any] | None:
        """Build the compensation command payload. Returns None if step is not compensatable."""
        ...

    def on_reply(self, step_index: int, context: dict[str, Any], result_data: dict[str, Any] | None) -> dict[str, Any]:
        """Merge reply data into saga context. Default: shallow merge result_data."""
        if result_data:
            context.update(result_data)
        return context
