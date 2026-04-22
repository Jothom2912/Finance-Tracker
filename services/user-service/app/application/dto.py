from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

USERNAME_MIN = 3
USERNAME_MAX = 50
EMAIL_MAX = 255
PASSWORD_MIN = 8
PASSWORD_MAX = 128


class RegisterDTO(BaseModel):
    username: str = Field(
        ...,
        min_length=USERNAME_MIN,
        max_length=USERNAME_MAX,
    )
    email: EmailStr
    password: str = Field(
        ...,
        min_length=PASSWORD_MIN,
        max_length=PASSWORD_MAX,
    )


class LoginDTO(BaseModel):
    username_or_email: str = Field(..., min_length=1, max_length=EMAIL_MAX)
    password: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    username: str


class ExistsResponse(BaseModel):
    exists: bool
