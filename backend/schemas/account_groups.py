from pydantic import BaseModel
from typing import Optional, List

# Forward references for relationships (minimal info)
class UserBase(BaseModel):
    idUser: int
    username: str
    class Config:
        from_attributes = True

# --- Base Schema ---
class AccountGroupsBase(BaseModel):
    name: Optional[str] = None

# --- Schema for creation (requires a list of User IDs) ---
class AccountGroupsCreate(AccountGroupsBase):
    user_ids: List[int] # Til håndtering af mange-til-mange relationen

# --- Schema for reading data (includes relationships) ---
class AccountGroups(AccountGroupsBase):
    idAccountGroups: int
    
    # Relationships
    users: List[UserBase] = []

    class Config:
        from_attributes = True