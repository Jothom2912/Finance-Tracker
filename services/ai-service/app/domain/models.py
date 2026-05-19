"""Domain models for the chat streaming pipeline.

Bruger discriminated union pattern (Pydantic Field(discriminator=...)) for stream
events. Det giver os tre ting: (1) hvert pipeline-step producerer typed events der
serialiseres direkte til SSE-frames uden manuelt dict-building, (2) Pydantic
validerer event-strukturen ved konstruktion og fanger kontraktbrud før de når
netværket, og (3) frontend kan switche på `event`-feltet for at dispatche til den
korrekte React-komponent — Pythons exhaustive pattern matching spejlet i
TypeScripts discriminated unions.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

# --- Enums ---


class IntentName(str, Enum):
    LARGEST_EXPENSE = "largest_expense"
    CATEGORY_BREAKDOWN = "category_breakdown"
    TRANSACTION_SEARCH = "transaction_search"
    BUDGET_STATUS = "budget_status"


class DataKind(str, Enum):
    TRANSACTION_LIST = "transaction_list"
    CATEGORY_BREAKDOWN = "category_breakdown"
    SINGLE_VALUE = "single_value"
    BUDGET_STATUS = "budget_status"


# --- Core domain models ---


class ResolvedIntent(BaseModel):
    intent: IntentName
    period: str = Field(description="YYYY-MM format, e.g. 2026-04")
    slots: dict[str, Any] = Field(default_factory=dict)


class TransactionItem(BaseModel):
    id: int
    date: str
    amount: float
    category: str
    description: str


class CategoryBreakdownItem(BaseModel):
    category: str
    amount: float
    percentage: float


class BudgetStatusItem(BaseModel):
    category_name: str
    budget_amount: float
    spent_amount: float
    remaining_amount: float
    percentage_used: float


# --- Payload containers ---


class TransactionListPayload(BaseModel):
    items: list[TransactionItem]
    highlight_id: int | None = None


class CategoryBreakdownPayload(BaseModel):
    items: list[CategoryBreakdownItem]
    total: float


class SingleValuePayload(BaseModel):
    value: float
    currency: str = "kr"
    label: str


class BudgetStatusPayload(BaseModel):
    items: list[BudgetStatusItem]
    total_budget: float
    total_spent: float
    total_remaining: float
    over_budget_count: int


class StreamMetadata(BaseModel):
    router_ms: float
    dispatch_ms: float
    responder_ms: float
    total_tokens: int


# --- Event data containers ---


class DataReadyData(BaseModel):
    kind: DataKind
    payload: (
        TransactionListPayload
        | CategoryBreakdownPayload
        | SingleValuePayload
        | BudgetStatusPayload
    )


class ProseChunkData(BaseModel):
    delta: str


class DoneData(BaseModel):
    metadata: StreamMetadata


class ErrorData(BaseModel):
    code: str
    message: str


# --- Stream event types (discriminated union) ---


class IntentResolvedEvent(BaseModel):
    event: Literal["intent_resolved"] = "intent_resolved"
    data: ResolvedIntent


class DataReadyEvent(BaseModel):
    event: Literal["data_ready"] = "data_ready"
    data: DataReadyData


class ProseChunkEvent(BaseModel):
    event: Literal["prose_chunk"] = "prose_chunk"
    data: ProseChunkData


class DoneEvent(BaseModel):
    event: Literal["done"] = "done"
    data: DoneData


class ErrorEvent(BaseModel):
    event: Literal["error"] = "error"
    data: ErrorData


ChatStreamEvent = Annotated[
    IntentResolvedEvent
    | DataReadyEvent
    | ProseChunkEvent
    | DoneEvent
    | ErrorEvent,
    Field(discriminator="event"),
]
