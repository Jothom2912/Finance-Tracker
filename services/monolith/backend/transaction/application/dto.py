"""DTOs for Transaction bounded context."""

from __future__ import annotations

from datetime import date, datetime
from datetime import date as date_type
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.transaction.domain.entities import TransactionType
from backend.validation_boundaries import PLANNED_TRANSACTION_BVA


# --- Forward references for nested relations ---
class CategoryBase(BaseModel):
    idCategory: int
    name: str
    model_config = ConfigDict(from_attributes=True)


class AccountBase(BaseModel):
    idAccount: int
    name: str
    model_config = ConfigDict(from_attributes=True)


# --- Transaction schemas ---


class TransactionBase(BaseModel):
    """Common fields for transaction creation and reading."""

    amount: float = Field(
        ..., description="Transaction amount. Must NOT be 0. Can be positive (income) or negative (expense)."
    )
    description: Optional[str] = Field(None, max_length=255, description="Optional transaction description")
    date: date_type = Field(
        default_factory=date_type.today, description="Transaction date (defaults to today if not provided)"
    )
    type: TransactionType

    @field_validator("amount")
    @classmethod
    def validate_amount_not_zero(cls, v: float) -> float:
        """BVA: Amount må IKKE være 0"""
        if v == 0 or abs(v) < 0.001:
            raise ValueError("Transaction amount cannot be zero (0)")
        return round(v, 2)

    @field_validator("date", mode="before")
    @classmethod
    def parse_date(cls, v):
        """Parser date fra string, datetime eller date objekt."""
        if v is None:
            return date_type.today()
        if isinstance(v, date_type):
            return v
        if isinstance(v, datetime):
            return v.date()
        if isinstance(v, str):
            try:
                return datetime.fromisoformat(v.replace("Z", "+00:00")).date()
            except Exception:
                try:
                    return datetime.strptime(v, "%d-%m-%Y").date()
                except Exception:
                    try:
                        return datetime.strptime(v, "%Y-%m-%d").date()
                    except Exception:
                        raise ValueError(f"Invalid date format: {v}")
        return v

    @field_validator("date")
    @classmethod
    def validate_date(cls, v: date_type) -> date_type:
        """BVA: Transaction date cannot be in the future."""
        if v > date_type.today():
            raise ValueError(f"Transaction date cannot be in the future. Got: {v}, Today: {date_type.today()}")
        return v

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )


class TransactionCreate(TransactionBase):
    """Fields required to create a new transaction."""

    category_id: int = Field(..., validation_alias="category_id", serialization_alias="Category_idCategory")
    account_id: Optional[int] = Field(None, validation_alias="account_id", serialization_alias="Account_idAccount")


class Transaction(TransactionBase):
    """Full schema including ID and relationships."""

    id: int = Field(serialization_alias="idTransaction")

    category_id: int = Field(serialization_alias="Category_idCategory")
    account_id: int = Field(serialization_alias="Account_idAccount")

    created_at: Optional[datetime] = Field(
        None, description="Timestamp for when the transaction was created (auto-generated)"
    )

    category: Optional[CategoryBase] = None
    account: Optional[AccountBase] = None

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )


# --- Planned transaction forward reference ---
class PlannedTransactionRefBase(BaseModel):
    idTransaction: int
    description: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


# --- Planned transaction schemas ---


class PlannedTransactionsBase(BaseModel):
    name: Optional[str] = Field(default=None, max_length=45, description="Name/description of planned transaction")
    amount: float = Field(..., description="Planned transaction amount. Must NOT be 0.")
    planned_date: Optional[date] = Field(
        default=None, description="Planned transaction date (must be future or current date, not past)"
    )
    repeat_interval: Optional[str] = Field(default=None, description="Repeat interval: daily, weekly, or monthly")

    @field_validator("amount")
    @classmethod
    def validate_amount_not_zero(cls, v: float) -> float:
        """BVA: Amount må IKKE være 0"""
        if abs(v) < 0.001:
            raise ValueError("Amount må IKKE være 0")
        return round(v, 2)

    @field_validator("planned_date")
    @classmethod
    def validate_planned_date(cls, v: Optional[date]) -> Optional[date]:
        """BVA: Planned date must be today or in the future."""
        if v is not None:
            today = date.today()
            if v < today:
                raise ValueError(f"Planned date må ikke være i fortiden. Today: {today}, Got: {v}")
        return v

    @field_validator("repeat_interval")
    @classmethod
    def validate_repeat_interval(cls, v: Optional[str]) -> Optional[str]:
        """BVA: Repeat interval må være daily, weekly eller monthly"""
        if v is not None and v not in PLANNED_TRANSACTION_BVA.valid_intervals:
            raise ValueError(f"Repeat interval må være en af {PLANNED_TRANSACTION_BVA.valid_intervals}, fik: {v}")
        return v


class PlannedTransactionsCreate(PlannedTransactionsBase):
    pass


class PlannedTransactions(PlannedTransactionsBase):
    id: int = Field(serialization_alias="idPlannedTransactions")
    transaction_id: Optional[int] = Field(None, serialization_alias="Transaction_idTransaction")

    transaction: Optional[PlannedTransactionRefBase] = None

    model_config = ConfigDict(
        from_attributes=True,
    )


# Backward-compatible aliases
TransactionCreateDTO = TransactionCreate
TransactionResponseDTO = Transaction
TransactionTypeDTO = TransactionType
PlannedTransactionCreateDTO = PlannedTransactionsCreate
PlannedTransactionUpdateDTO = PlannedTransactionsBase
PlannedTransactionResponseDTO = PlannedTransactions
