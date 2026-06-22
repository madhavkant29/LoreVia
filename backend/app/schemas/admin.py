import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class RateLimitOverrideBody(BaseModel):
    search_per_hour: int | None = None
    summary_per_hour: int | None = None
    chat_per_day: int | None = None
    api_per_minute: int | None = None


class UpdateUserTierBody(BaseModel):
    tier: str


class AdminSessionOut(BaseModel):
    is_admin: bool
    scopes: list[str]
    is_owner: bool
    requires_step_up: bool
    session_expires_at: datetime | None = None


class AdminStepUpBody(BaseModel):
    password: str = Field(min_length=1)


class AdminPrincipalGrantBody(BaseModel):
    user_id: uuid.UUID
    scopes: list[str] = Field(default_factory=list)
    is_owner: bool = False
    reason: str = Field(min_length=1)


class AdminPrincipalRevokeBody(BaseModel):
    reason: str = Field(min_length=1)


class AdminPrincipalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    status: str
    is_owner: bool
    scopes: list[str]
    grant_reason: str
    revoke_reason: str | None = None
    granted_by_user_id: uuid.UUID | None = None
    revoked_by_user_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime
    revoked_at: datetime | None = None


class AdminAuditEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    actor_user_id: uuid.UUID | None = None
    target_user_id: uuid.UUID | None = None
    target_book_id: uuid.UUID | None = None
    target_report_id: uuid.UUID | None = None
    target_refund_review_id: uuid.UUID | None = None
    action_type: str
    reason: str | None = None
    result: str
    request_id: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    scopes_snapshot: list[str]
    metadata_json: dict
    created_at: datetime


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
    reason: str | None = None


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
    reason: str = Field(min_length=1)


class AdminRestoreBookBody(BaseModel):
    reason: str = Field(min_length=1)


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


class RefundReviewCreateBody(BaseModel):
    transaction_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    request_source: str = Field(min_length=1)
    support_reference: str | None = None


class RefundReviewDecisionBody(BaseModel):
    reason: str = Field(min_length=1)
    provider_followup_only: bool = False


class RefundReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    subscription_id: uuid.UUID | None = None
    paddle_transaction_id: str
    paddle_adjustment_id: str | None = None
    charge_at: datetime | None = None
    plan_code: str
    billing_interval: str
    request_source: str
    support_reference: str | None = None
    request_reason: str
    status: str
    auto_decision: bool | None = None
    decision_reason: str | None = None
    eligibility_snapshot_json: dict
    usage_snapshot_json: dict
    provider_response_json: dict
    requested_by_admin_user_id: uuid.UUID | None = None
    resolved_by_admin_user_id: uuid.UUID | None = None
    resolved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class AdminTaskActionBody(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)


class SupportIncidentCreateBody(BaseModel):
    user_id: uuid.UUID | None = None
    book_id: uuid.UUID | None = None
    task_execution_id: uuid.UUID | None = None
    category: str = Field(min_length=1, max_length=120)
    feature: str | None = Field(default=None, max_length=120)
    severity: str = Field(default="medium", pattern="^(low|medium|high|critical)$")
    summary: str = Field(min_length=1, max_length=1000)


class SupportIncidentResolveBody(BaseModel):
    resolution: str = Field(min_length=1, max_length=4000)
