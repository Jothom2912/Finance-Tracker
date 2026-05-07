from __future__ import annotations

from datetime import date
from typing import Optional

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


class Goal(GoalBase):
    idGoal: Optional[int] = None
    Account_idAccount: int
    model_config = ConfigDict(from_attributes=True)
