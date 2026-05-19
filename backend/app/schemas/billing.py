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


class CheckoutBody(BaseModel):
    plan: PaidPlanCode


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
