from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

PaidPlanCode = Literal[
    "author_monthly",
    "author_annual",
    "architect_monthly",
    "architect_annual",
    "power_monthly",
    "power_annual",
]


class CheckoutPreviewBody(BaseModel):
    plan: PaidPlanCode


class CheckoutBody(CheckoutPreviewBody):
    confirmed_immediate_charge: bool = False
    quote_token: str | None = None


class CheckoutAbandonBody(BaseModel):
    transaction_id: str = Field(min_length=1, max_length=100)


class CheckoutPreviewOut(BaseModel):
    plan: PaidPlanCode
    display_name: str
    billing_interval: Literal["monthly", "annual"]
    trial_status: Literal["active", "expired"]
    trial_active: bool
    trial_ends_at: datetime | None = None
    charge_today: str
    recurring_price: str
    confirmation_required: bool
    confirmation_text: str | None = None
    checkout_button_label: str
    default_action_label: str | None = None
    quote_token: str | None = None
    billing_enabled: bool = True
    message: str | None = None


class CheckoutAbandonOut(BaseModel):
    abandoned: bool
    transaction_id: str
    status: str


class BillingConfirmationOut(BaseModel):
    transaction_id: str
    status: str
    plan: str
    billing_interval: Literal["monthly", "annual"]
    display_name: str
    currency_code: str | None = None
    total: str | None = None
    invoice_number: str | None = None
    invoice_pdf_url: str | None = None
    subscription_id: str | None = None
    customer_email: str | None = None


class BillingPlanStatusOut(BaseModel):
    code: str
    display_name: str
    billing_interval: Literal["monthly", "annual"]
    price_usd: int
    configured: bool
    price_id_present: bool


class BillingSubscriptionPriceOut(BaseModel):
    amount: int
    currency: str
    interval: Literal["month", "year"]


BillingDisplayState = Literal[
    "free",
    "trial",
    "active",
    "cancellation_scheduled",
    "past_due",
    "paused",
    "canceled",
]


class BillingSubscriptionOut(BaseModel):
    plan: str
    plan_tier: str
    status: str
    display_state: BillingDisplayState
    price: BillingSubscriptionPriceOut
    current_period_start: datetime | None = None
    current_period_end: datetime | None = None
    cancel_at_period_end: bool = False
    cancellation_scheduled_at: datetime | None = None
    next_charge_at: datetime | None = None
    auto_renew: bool = False
    last_payment_status: str | None = None
    has_paddle_subscription: bool = False


class BillingStatusOut(BaseModel):
    billing_enabled: bool
    payments_ready: bool
    paddle_api_key_present: bool
    webhook_secret_present: bool
    default_checkout_url_present: bool
    recommended_default_checkout_url: str
    resend_api_key_present: bool
    internal_job_secret_present: bool
    fully_configured_plan_count: int
    missing_configuration: list[str] = Field(default_factory=list)
    plans: list[BillingPlanStatusOut] = Field(default_factory=list)
    webhook_endpoint_path: str
    supported_webhook_events: list[str] = Field(default_factory=list)
    trial_email_job_endpoint_path: str
    trial_email_runner_script: str
    trial_email_automation_code_ready: bool
    priority_processing_code_ready: bool
    priority_queue_names: list[str] = Field(default_factory=list)
    external_action_items: list[str] = Field(default_factory=list)
