from pydantic import BaseModel, Field, field_validator, ConfigDict
from datetime import date, datetime
from typing import Optional
from backend.validation_boundaries import GOAL_BVA

# Forward references for relationships (minimal info)
class AccountBase(BaseModel):
    idAccount: int
    name: str
    model_config = ConfigDict(from_attributes=True)

# --- Base Schema ---
class GoalBase(BaseModel):
    name: Optional[str] = Field(
        default=None,
        max_length=45,
        description="Goal name"
    )
    target_amount: float = Field(
        ...,
        ge=0,  # BVA: must be >= 0
        description="Target amount (must be >= 0). Grænser: -0.01 (ugyldig), 0 (gyldig), 0.01 (gyldig)"
    )
    current_amount: float = Field(
        default=0.00,
        ge=0,  # BVA: must be >= 0
        description="Current amount (must be >= 0). Grænser: -0.01 (ugyldig), 0 (gyldig), 0.01 (gyldig)"
    )
    target_date: Optional[date] = Field(
        default=None,
        description="Deadline for goal (must be future date)"
    )
    status: Optional[str] = Field(
        default=None,
        description="Goal status (e.g., 'active', 'completed')"
    )

    @field_validator('target_amount')
    @classmethod
    def validate_target_amount(cls, v: float) -> float:
        """BVA: Target amount må være >= 0"""
        if v < 0:
            raise ValueError(f"Target amount må være >= 0, fik: {v}")
        return round(v, 2)

    @field_validator('current_amount')
    @classmethod
    def validate_current_amount(cls, v: float) -> float:
        """BVA: Current amount må være >= 0"""
        if v < 0:
            raise ValueError(f"Current amount må være >= 0, fik: {v}")
        return round(v, 2)

    @field_validator('current_amount')
    @classmethod
    def validate_current_vs_target(cls, v: float, info) -> float:
        """BVA: currentAmount må IKKE være større end targetAmount

        Grænseværdier:
        - Target = 100, Current = 101 (ugyldig)
        - Target = 100, Current = 100 (gyldig)
        - Target = 100, Current = 99 (gyldig)
        """
        if 'target_amount' in info.data:
            target = info.data['target_amount']
            if v > target:
                raise ValueError(
                    f"Current amount ({v}) kan ikke være større end target amount ({target})"
                )
        return v

    @field_validator('target_date')
    @classmethod
    def validate_target_date(cls, v: Optional[date]) -> Optional[date]:
        """BVA: Target date skal være i fremtiden (future date)

        Grænseværdier:
        - Dato i fortiden (ugyldig)
        - Dato i dag (ugyldig)
        - Dato i morgen (gyldig)
        """
        if v is not None:
            today = date.today()
            if v <= today:
                raise ValueError(
                    f"Deadline skal være i fremtiden. "
                    f"Got: {v}, Today: {today}"
                )
        return v


# --- Schema for creation (requires Account ID) ---
class GoalCreate(GoalBase):
    Account_idAccount: int


# --- Schema for reading data (includes relationship) ---
class Goal(GoalBase):
    idGoal: int
    Account_idAccount: Optional[int] = None  # Gør optional

    # Relationship is optional to keep schema stable across adapters.
    account: Optional[AccountBase] = None  # Gør optional

    model_config = ConfigDict(
        from_attributes=True,
    )