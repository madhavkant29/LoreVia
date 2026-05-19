from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterBody(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=32)
    password: str = Field(..., min_length=12, max_length=128)
    accepted_terms: bool
    device_id: str = Field(..., min_length=16, max_length=128)


class LoginBody(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    username: str | None = None
    tier: str
    plan_tier: str
    tier_label: str
    trial_active: bool
    trial_ends_at: datetime | None = None
    reading_mode: str
    daily_word_goal: int
    today_word_count: int
    last_login_at: datetime | None = None
    login_streak_days: int
    longest_login_streak_days: int
    login_activity_dates: list[date] = Field(default_factory=list)
    email_verified: bool
    messaging_permission: str
    created_at: datetime


class DailyWordGoalBody(BaseModel):
    daily_word_goal: int = Field(..., ge=1, le=1000000)


class MessagingPermissionBody(BaseModel):
    messaging_permission: str = Field(..., pattern="^(anyone|friends_only)$")


class RegisterOut(BaseModel):
    id: uuid.UUID
    email: str
    username: str
    email_verification_required: bool = True
    verification_email_sent: bool = True
    verification_url: str | None = None


class VerifyEmailBody(BaseModel):
    token: str


class VerifyEmailResendBody(BaseModel):
    email: EmailStr


class SupabaseOAuthBody(BaseModel):
    token: str
    accepted_terms: bool = False
    device_id: str = Field(..., min_length=16, max_length=128)


class ForgotPasswordBody(BaseModel):
    email: EmailStr


class ResetPasswordBody(BaseModel):
    token: str = Field(..., min_length=20, max_length=256)
    password: str = Field(..., min_length=12, max_length=128)


class RefreshBody(BaseModel):
    refresh_token: str


class TierLimitsOut(BaseModel):
    free_max_books: int
    author_max_uploads: int
    architect_uploads_unlimited: bool = True
    free_total_token_budget: int
    free_search_per_day: int
    free_summary_per_hour: int
    free_prediction_per_day: int
    free_recall_per_day: int
    author_prediction_per_day: int
    architect_prediction_per_day: int
    trial_high_cost_turns_per_day: int
    author_high_cost_turns_per_day: int
    architect_high_cost_turns_per_day: int
    free_advisor_per_day: int
    free_advisor_per_week: int
    free_advisor_per_month: int
    free_continuity_per_day: int
    author_advisor_per_day: int
    author_advisor_per_week: int
    author_advisor_per_month: int
    architect_advisor_per_day: int
    architect_advisor_per_week: int
    architect_advisor_per_month: int
    free_continuity_per_minute: int
    author_continuity_per_minute: int
    architect_continuity_per_minute: int
