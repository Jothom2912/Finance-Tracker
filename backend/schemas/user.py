from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional, List

# Forward references for relationships
class AccountBase(BaseModel):
    idAccount: int
    name: str
    saldo: float
    class Config:
        from_attributes = True

class AccountGroupsBase(BaseModel):
    idAccountGroups: int
    name: Optional[str] = None
    class Config:
        from_attributes = True

# --- Base Schema ---
class UserBase(BaseModel):
    username: str
    email: EmailStr

# --- Schema for creation (requires password) ---
class UserCreate(UserBase):
    password: str

# --- Schema for reading data (includes IDs and relationships) ---
class User(UserBase):
    idUser: int
    created_at: datetime
    
    # Relationships
    accounts: List[AccountBase] = []
    account_groups: List[AccountGroupsBase] = []

    class Config:
        # Erstattet `from_orm = True` med `from_attributes = True` for Pydantic v2
        from_attributes = True