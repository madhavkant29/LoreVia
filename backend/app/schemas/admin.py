from datetime import date, datetime

from pydantic import BaseModel


class RateLimitOverrideBody(BaseModel):
    search_per_hour: int | None = None
    summary_per_hour: int | None = None
    chat_per_day: int | None = None
    api_per_minute: int | None = None


class UpdateUserTierBody(BaseModel):
    tier: str


class SubscriptionMetricsOut(BaseModel):
    cohort_start: date
    cohort_end: date
    trial_starts: int
    trial_to_paid_conversions: int
    trial_to_paid_rate: float | None = None
    cancellation_events: int
    resolved_cancellation_events: int
    unresolved_cancellation_events: int
    reactivated_after_cancellation: int
    churned_after_cancellation: int
    post_cancel_churn_rate: float | None = None
    reactivation_window_days: int


class PublicShareApprovalBody(BaseModel):
    approved: bool = True


class PendingPublicShareOut(BaseModel):
    book_id: str
    user_id: str
    author_username: str | None = None
    title: str
    author: str | None = None
    genre: str | None = None
    isbn: str | None = None
    copyright_warning: bool = False
    public_description: str | None = None
    requested_at: datetime | None = None
    created_at: datetime


class AdminBookModerationBody(BaseModel):
    reason: str


class AdminRestoreBookBody(BaseModel):
    reason: str | None = None


class CreatorStrikeCreateBody(BaseModel):
    book_id: str | None = None
    report_id: str | None = None
    strike_type: str
    severity: str
    reason: str


class ContentReportAdminOut(BaseModel):
    id: str
    reported_book_id: str
    reported_author_user_id: str | None = None
    reporter_user_id: str | None = None
    reporter_email: str | None = None
    report_type: str
    status: str
    reason: str
    details: str | None = None
    created_at: datetime


class CreatorStrikeOut(BaseModel):
    id: str
    user_id: str
    book_id: str | None = None
    report_id: str | None = None
    strike_type: str
    severity: str
    reason: str
    is_active: bool
    created_at: datetime
