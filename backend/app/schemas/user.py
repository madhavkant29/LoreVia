import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr = Field(..., max_length=255)
    password: str = Field(..., min_length=8, max_length=128)


class UserLogin(BaseModel):
    email: EmailStr = Field(..., max_length=255)
    password: str = Field(..., max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    username: str | None = None
    tier: str
    reading_mode: str
    daily_word_goal: int
    today_word_count: int
    last_login_at: datetime | None = None
    login_streak_days: int
    longest_login_streak_days: int
    login_activity_dates: list[date] = Field(default_factory=list)
    created_at: datetime
