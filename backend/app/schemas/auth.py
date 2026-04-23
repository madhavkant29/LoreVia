from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterBody(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=12, max_length=128)
    accepted_terms: bool


class LoginBody(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    tier: str
    reading_mode: str
    created_at: datetime


class SupabaseOAuthBody(BaseModel):
    token: str
    accepted_terms: bool = False


class ForgotPasswordBody(BaseModel):
    email: EmailStr


class ResetPasswordBody(BaseModel):
    token: str
    password: str = Field(..., min_length=12, max_length=128)


class RefreshBody(BaseModel):
    refresh_token: str
