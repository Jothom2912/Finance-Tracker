from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from app.domain.entities import GoalStatus
from pydantic import BaseModel, ConfigDict, Field, field_validator


class GoalBase(BaseModel):
    name: Optional[str] = Field(default=None, max_length=45)
    target_amount: float = Field(..., ge=0)
    current_amount: float = Field(default=0.0, ge=0)
    target_date: Optional[date] = None
    status: Optional[str] = None

    @field_validator("target_amount")
    @classmethod
    def validate_target_amount(cls, value: float) -> float:
        return round(value, 2)

    @field_validator("current_amount")
    @classmethod
    def validate_current_amount(cls, value: float) -> float:
        return round(value, 2)


class GoalCreate(GoalBase):
    Account_idAccount: int


class GoalResponse(BaseModel):
    idGoal: Optional[int] = None
    name: Optional[str] = None
    target_amount: float
    current_amount: float
    target_date: Optional[date] = None
    status: GoalStatus
    effective_status: GoalStatus
    progress_percent: float
    Account_idAccount: int
    is_default_savings_goal: bool = False
    model_config = ConfigDict(from_attributes=True)


class AllocationHistoryEntryResponse(BaseModel):
    amount: float
    source_key: str
    applied_at: datetime
    model_config = ConfigDict(from_attributes=True)


class UnallocatedSurplusEntryResponse(BaseModel):
    amount: float
    reason: str
    observed_at: datetime
    model_config = ConfigDict(from_attributes=True)


class UnallocatedSurplusResponse(BaseModel):
    total: float
    entries: list[UnallocatedSurplusEntryResponse]


# Keep backward-compatible alias used by existing imports in service/tests.
Goal = GoalResponse
