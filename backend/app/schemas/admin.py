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
    public_description: str | None = None
    requested_at: datetime | None = None
    created_at: datetime
