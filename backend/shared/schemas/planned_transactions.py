from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional
from datetime import date, datetime
from decimal import Decimal
from backend.validation_boundaries import PLANNED_TRANSACTION_BVA

# Forward references for relationships (minimal info)
class TransactionBase(BaseModel):
    idTransaction: int
    description: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

# --- Base Schema ---
class PlannedTransactionsBase(BaseModel):
    name: Optional[str] = Field(
        default=None,
        max_length=45,
        description="Name/description of planned transaction"
    )
    amount: float = Field(
        ...,
        description="Planned transaction amount. Must NOT be 0."
    )
    planned_date: Optional[date] = Field(
        default=None,
        description="Planned transaction date (must be future or current date, not past)"
    )
    repeat_interval: Optional[str] = Field(
        default=None,
        description="Repeat interval: daily, weekly, or monthly"
    )

    @field_validator('amount')
    @classmethod
    def validate_amount_not_zero(cls, v: float) -> float:
        """BVA: Amount må IKKE være 0
        
        Grænseværdier:
        - -0.01 (gyldig)
        - 0 (ugyldig)
        - 0.01 (gyldig)
        """
        if abs(v) < 0.001:  # Håndterer floating point precision
            raise ValueError("Amount må IKKE være 0")
        return round(v, 2)

    @field_validator('planned_date')
    @classmethod
    def validate_planned_date(cls, v: Optional[date]) -> Optional[date]:
        """BVA: Planned date skal være i fremtiden eller i dag (ikke fortid)
        
        Grænseværdier:
        - Gårsdagens dato (ugyldig)
        - Dagens dato (gyldig)
        - Morgendagens dato (gyldig)
        """
        if v is not None:
            today = date.today()
            if v < today:
                raise ValueError(
                    f"Planned date må ikke være i fortiden. "
                    f"Today: {today}, Got: {v}"
                )
        return v

    @field_validator('repeat_interval')
    @classmethod
    def validate_repeat_interval(cls, v: Optional[str]) -> Optional[str]:
        """BVA: Repeat interval må være daily, weekly eller monthly"""
        if v is not None and v not in PLANNED_TRANSACTION_BVA.valid_intervals:
            raise ValueError(
                f"Repeat interval må være en af {PLANNED_TRANSACTION_BVA.valid_intervals}, "
                f"fik: {v}"
            )
        return v

# --- Schema for creation ---
class PlannedTransactionsCreate(PlannedTransactionsBase):
    # Tillader at en planlagt transaktion oprettes uden en allerede eksisterende transaktion
    pass

# --- Schema for reading data (includes relationship) ---
class PlannedTransactions(PlannedTransactionsBase):
    idPlannedTransactions: int
    Transaction_idTransaction: Optional[int] = None
    
    # Relationship
    transaction: Optional[TransactionBase] = None  # Kan være NULL

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            Decimal: lambda v: float(v),
        }
    )