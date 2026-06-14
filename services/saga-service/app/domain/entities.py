from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4


class SagaStatus(StrEnum):
    STARTED = "started"
    COMPENSATING = "compensating"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


class StepStatus(StrEnum):
    PENDING = "pending"
    EXECUTING = "executing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    COMPENSATED = "compensated"


@dataclass
class SagaStep:
    """Immutable description of one step in a saga."""

    index: int
    name: str
    status: StepStatus = StepStatus.PENDING
    command_sent_at: datetime | None = None
    reply_received_at: datetime | None = None
    compensated_at: datetime | None = None
    error_detail: str | None = None


@dataclass
class SagaInstance:
    """Aggregate root representing a running saga."""

    id: str = field(default_factory=lambda: str(uuid4()))
    saga_type: str = ""
    correlation_id: str = field(default_factory=lambda: str(uuid4()))
    current_step: int = 0
    status: SagaStatus = SagaStatus.STARTED
    context: dict[str, Any] = field(default_factory=dict)
    steps: list[SagaStep] = field(default_factory=list)
    error_detail: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    updated_at: datetime | None = None

    @property
    def is_active(self) -> bool:
        return self.status in (SagaStatus.STARTED, SagaStatus.COMPENSATING)

    @property
    def current_step_obj(self) -> SagaStep | None:
        if 0 <= self.current_step < len(self.steps):
            return self.steps[self.current_step]
        return None

    @property
    def is_last_step(self) -> bool:
        return self.current_step >= len(self.steps) - 1
