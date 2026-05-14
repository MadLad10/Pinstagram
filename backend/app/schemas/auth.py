import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, field_validator


class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    name: str

    @field_validator("password")
    @classmethod
    def password_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Name cannot be empty")
        return v.strip()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class GoogleAuthRequest(BaseModel):
    id_token: str


class RefreshRequest(BaseModel):
    refresh_token: str


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    code: str


class UserRead(BaseModel):
    id: uuid.UUID
    email: str
    name: str
    bio: str | None
    avatar_url: str | None
    location: str | None
    is_private: bool
    is_verified: bool
    role: str
    is_premium: bool
    email_verified: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AuthResponse(BaseModel):
    user: UserRead
    access_token: str
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
