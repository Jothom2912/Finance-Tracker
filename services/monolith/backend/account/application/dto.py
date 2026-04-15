"""Data Transfer Objects for Account bounded context.

Pydantic schemas for Account and AccountGroups use cases.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.shared.budget_period import MAX_START_DAY, MIN_START_DAY
from backend.validation_boundaries import ACCOUNT_BVA, ACCOUNT_GROUP_BVA


# Forward references for relationships (minimal info)
class UserBase(BaseModel):
    idUser: int
    username: str
    model_config = ConfigDict(from_attributes=True)


class TransactionBase(BaseModel):
    idTransaction: int
    amount: float
    type: str
    model_config = ConfigDict(from_attributes=True)


class BudgetBase(BaseModel):
    idBudget: int
    amount: float
    model_config = ConfigDict(from_attributes=True)


class GoalBase(BaseModel):
    idGoal: int
    name: Optional[str] = None
    status: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


# --- Account Base Schema ---
class AccountBase(BaseModel):
    name: str = Field(
        ...,
        min_length=ACCOUNT_BVA.name_min_length,  # 1 char
        max_length=ACCOUNT_BVA.name_max_length,  # 30 chars
        description="Account name (1-30 characters)",
    )
    saldo: float = Field(default=0.00, description="Current account balance (can be negative or positive)")
    budget_start_day: int = Field(
        default=1,
        ge=MIN_START_DAY,
        le=MAX_START_DAY,
        description=f"Day of month when budget period starts ({MIN_START_DAY}-{MAX_START_DAY})",
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """BVA: Account name må ikke være tomt eller kun mellemrum"""
        if not v or v.strip() == "":
            raise ValueError("Account name må ikke være tomt")
        return v.strip()

    @field_validator("saldo")
    @classmethod
    def validate_saldo(cls, v: float) -> float:
        """BVA: Saldo skal være valideret (kan være negativ eller positiv)"""
        return round(v, 2)


# --- Account Schema for creation (requires User ID) ---
class AccountCreate(AccountBase):
    User_idUser: int


# --- Account Schema for reading data (includes relationships) ---
class Account(AccountBase):
    idAccount: int
    User_idUser: Optional[int] = None  # Gør optional (Neo4j returnerer måske None)

    # Relationships are optional to keep schema stable across adapters.
    user: Optional[UserBase] = None  # Gør optional (repositories returnerer ikke nested objects)
    transactions: Optional[List[TransactionBase]] = []
    budgets: Optional[List[BudgetBase]] = []
    goals: Optional[List[GoalBase]] = []

    model_config = ConfigDict(
        from_attributes=True,
    )


# --- AccountGroups Base Schema ---
class AccountGroupsBase(BaseModel):
    name: str = Field(
        ...,
        min_length=ACCOUNT_GROUP_BVA.name_min_length,  # 1 char
        max_length=ACCOUNT_GROUP_BVA.name_max_length,  # 30 chars
        description="Group name (1-30 characters)",
    )
    max_users: int = Field(
        default=ACCOUNT_GROUP_BVA.max_users,
        le=ACCOUNT_GROUP_BVA.max_users,  # <= 20
        ge=1,  # >= 1
        description=f"Maximum number of users allowed in group (max {ACCOUNT_GROUP_BVA.max_users})",
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """BVA: Group name må ikke være tomt eller kun whitespace"""
        if not v or v.strip() == "":
            raise ValueError("Group name må ikke være tomt")
        return v.strip()

    @field_validator("max_users")
    @classmethod
    def validate_max_users(cls, v: int) -> int:
        """BVA: max_users grænseværdier: 19 (gyldig), 20 (gyldig/grænse), 21 (ugyldig)"""
        if v < 1:
            raise ValueError("max_users skal være mindst 1")
        if v > ACCOUNT_GROUP_BVA.max_users:
            raise ValueError(f"max_users kan ikke være større end {ACCOUNT_GROUP_BVA.max_users}, fik: {v}")
        return v


# --- AccountGroups Schema for creation (requires a list of User IDs) ---
class AccountGroupsCreate(AccountGroupsBase):
    user_ids: List[int] = Field(default=[], description="List of user IDs to add to the group")

    @field_validator("user_ids")
    @classmethod
    def validate_user_ids_count(cls, v: List[int], info) -> List[int]:
        """BVA: Antal brugere må ikke overstige max_users"""
        if "max_users" in info.data:
            max_users = info.data["max_users"]
            if len(v) > max_users:
                raise ValueError(f"Antal brugere ({len(v)}) kan ikke overstige max_users ({max_users})")
        return v


# --- AccountGroups Schema for reading data (includes relationships) ---
class AccountGroups(AccountGroupsBase):
    idAccountGroups: int

    # Relationships
    users: List[UserBase] = []

    model_config = ConfigDict(from_attributes=True)
