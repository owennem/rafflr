from pydantic import BaseModel, EmailStr, field_validator, Field
from datetime import datetime
from typing import Optional

from app.utils.validation import (
    validate_username,
    validate_password,
    MAX_USERNAME_LENGTH,
    MAX_EMAIL_LENGTH,
    MAX_PASSWORD_LENGTH,
)


class UserCreate(BaseModel):
    email: EmailStr = Field(..., max_length=MAX_EMAIL_LENGTH)
    username: str = Field(..., min_length=3, max_length=MAX_USERNAME_LENGTH)
    password: str = Field(..., min_length=8, max_length=MAX_PASSWORD_LENGTH)

    @field_validator("username")
    @classmethod
    def validate_username_field(cls, v: str) -> str:
        return validate_username(v)

    @field_validator("password")
    @classmethod
    def validate_password_field(cls, v: str) -> str:
        return validate_password(v)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None


class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    is_admin: bool
    is_verified: bool
    created_at: datetime

    class Config:
        from_attributes = True


class PasswordReset(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    user_id: Optional[int] = None
