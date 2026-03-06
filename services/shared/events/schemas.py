"""Shared event schemas for inter-service communication via RabbitMQ."""

from datetime import datetime

from pydantic import BaseModel, Field


class BaseEvent(BaseModel):
    event_id: str = Field(default="")
    event_type: str = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source_service: str = ""


class UserCreatedEvent(BaseEvent):
    event_type: str = "user.created"
    user_id: int = 0
    email: str = ""


class TransactionCreatedEvent(BaseEvent):
    event_type: str = "transaction.created"
    transaction_id: int = 0
    account_id: int = 0
    amount: float = 0.0


class BudgetExceededEvent(BaseEvent):
    event_type: str = "budget.exceeded"
    budget_id: int = 0
    category_id: int = 0
    current_spend: float = 0.0
    budget_limit: float = 0.0
