from pydantic import BaseModel, Field, field_validator, EmailStr
from datetime import datetime
from typing import Optional, List
import re
from backend.validation_boundaries import USER_BVA

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
    username: str = Field(
        ...,
        min_length=USER_BVA.username_min_length,      # 3 chars
        max_length=USER_BVA.username_max_length,      # 20 chars
        description="Username (3-20 characters, alphanumeric + underscore)"
    )
    email: EmailStr = Field(
        ...,
        description="Valid email address"
    )

    @field_validator('username')
    @classmethod
    def validate_username_format(cls, v: str) -> str:
        """BVA: Username må kun indeholde alphanumeriske tegn og underscore"""
        if not re.match(r"^\w+$", v):
            raise ValueError("Username må kun indeholde bogstaver, tal og underscore (_)")
        return v

    @field_validator('username')
    @classmethod
    def validate_username_not_empty(cls, v: str) -> str:
        """BVA: Username må ikke være tomt eller kun whitespace"""
        if not v or v.strip() == "":
            raise ValueError("Username må ikke være tomt")
        return v.strip()

    @field_validator('email')
    @classmethod
    def validate_email_format(cls, v: str) -> str:
        """BVA: Email skal være valid format (valideres af EmailStr)"""
        return v.lower()  # Normalisér til lowercase


# --- Schema for creation (requires password) ---
class UserCreate(UserBase):
    password: str = Field(
        ...,
        min_length=USER_BVA.password_min_length,      # 8 chars
        description="Password (minimum 8 characters)"
    )

    @field_validator('password')
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """BVA: Password skal være mindst 8 tegn
        
        Grænseværdier:
        - 7 chars (ugyldig)
        - 8 chars (gyldig)
        - 9+ chars (gyldig)
        """
        if len(v) < USER_BVA.password_min_length:
            raise ValueError(f"Password skal være mindst {USER_BVA.password_min_length} tegn")
        return v


# --- Schema for reading data (includes IDs and relationships) ---
class User(UserBase):
    idUser: int
    created_at: datetime
    
    # Relationships
    accounts: List[AccountBase] = []
    account_groups: List[AccountGroupsBase] = []

    class Config:
        from_attributes = True

# --- Schema for login (email + password) ---
class UserLogin(BaseModel):
    """Schema for login request (email or username + password)"""
    username_or_email: str = Field(
        ...,
        description="Username or email address"
    )
    password: str = Field(
        ...,
        description="Password"
    )


# --- Token response ---
class TokenResponse(BaseModel):
    """Response ved succesfuldt login"""
    access_token: str
    token_type: str
    user_id: int
    username: str
    email: str
    account_id: Optional[int] = None  # Første account ID hvis brugeren har accounts
    
    class Config:
        from_attributes = True