from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterBody(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=32)
    password: str = Field(..., min_length=12, max_length=128)
    accepted_terms: bool


class LoginBody(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    username: str | None = None
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


class TierLimitsOut(BaseModel):
    free_max_books: int
    free_total_token_budget: int
    free_search_per_hour: int
    free_summary_per_hour: int
    free_chat_per_day: int
    free_advisor_per_day: int
    free_advisor_per_week: int
    free_advisor_per_month: int
    pro_chat_per_day: int
    pro_advisor_per_day: int
    pro_advisor_per_week: int
    pro_advisor_per_month: int
    power_advisor_per_day: int
    power_advisor_per_week: int
    power_advisor_per_month: int
    free_continuity_per_minute: int
    pro_continuity_per_minute: int
    power_continuity_per_minute: int
