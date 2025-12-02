from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from ..validation_boundaries import ACCOUNT_GROUP_BVA

# Forward references for relationships (minimal info)
class UserBase(BaseModel):
    idUser: int
    username: str
    class Config:
        from_attributes = True

# --- Base Schema ---
class AccountGroupsBase(BaseModel):
    name: str = Field(
        ...,
        min_length=ACCOUNT_GROUP_BVA.name_min_length,    # 1 char
        max_length=ACCOUNT_GROUP_BVA.name_max_length,    # 30 chars
        description="Group name (1-30 characters)"
    )
    max_users: int = Field(
        default=ACCOUNT_GROUP_BVA.max_users,
        le=ACCOUNT_GROUP_BVA.max_users,                  # <= 20
        ge=1,                                             # >= 1
        description=f"Maximum number of users allowed in group (max {ACCOUNT_GROUP_BVA.max_users})"
    )

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """BVA: Group name må ikke være tomt eller kun whitespace"""
        if not v or v.strip() == "":
            raise ValueError("Group name må ikke være tomt")
        return v.strip()

    @field_validator('max_users')
    @classmethod
    def validate_max_users(cls, v: int) -> int:
        """BVA: max_users grænseværdier: 19 (gyldig), 20 (gyldig/grænse), 21 (ugyldig)"""
        if v < 1:
            raise ValueError("max_users skal være mindst 1")
        if v > ACCOUNT_GROUP_BVA.max_users:
            raise ValueError(
                f"max_users kan ikke være større end {ACCOUNT_GROUP_BVA.max_users}, fik: {v}"
            )
        return v

# --- Schema for creation (requires a list of User IDs) ---
class AccountGroupsCreate(AccountGroupsBase):
    user_ids: List[int] = Field(
        default=[],
        description="List of user IDs to add to the group"
    )

    @field_validator('user_ids')
    @classmethod
    def validate_user_ids_count(cls, v: List[int], info) -> List[int]:
        """BVA: Antal brugere må ikke overstige max_users"""
        if 'max_users' in info.data:
            max_users = info.data['max_users']
            if len(v) > max_users:
                raise ValueError(
                    f"Antal brugere ({len(v)}) kan ikke overstige max_users ({max_users})"
                )
        return v

# --- Schema for reading data (includes relationships) ---
class AccountGroups(AccountGroupsBase):
    idAccountGroups: int
    
    # Relationships
    users: List[UserBase] = []

    class Config:
        from_attributes = True