from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from datetime import datetime
from backend.models.user import UserRole

class UserBase(BaseModel):
    username: str
    email: EmailStr

    @field_validator('username')
    @classmethod
    def validate_username(cls, v: str) -> str:
        if len(v) < 3:
            raise ValueError('Brugernavn skal være mindst 3 tegn')
        if len(v) > 20:
            raise ValueError('Brugernavn må højst være 20 tegn')
        return v

class UserCreate(UserBase):
    password: str

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError('Password skal være mindst 8 tegn')
        return v

class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    is_active: Optional[int] = None

    @field_validator('username')
    @classmethod
    def validate_username(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if len(v) < 3:
            raise ValueError('Brugernavn skal være mindst 3 tegn')
        if len(v) > 20:
            raise ValueError('Brugernavn må højst være 20 tegn')
        return v

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if len(v) < 8:
            raise ValueError('Password skal være mindst 8 tegn')
        return v

class UserResponse(UserBase):
    idUser: int
    role: UserRole
    is_active: int
    created_at: datetime

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None

# Behold gammel User schema for bagudkompatibilitet
class User(UserResponse):
    pass