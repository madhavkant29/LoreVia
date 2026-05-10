from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException

from app.core.config import settings

FREE_TIER = "free"
READER_TIER = "reader"
AUTHOR_TIER = "author"
ARCHITECT_TIER = "architect"
ADMIN_TIER = "admin"

TRIAL_DAYS = 10
AUTHOR_ACCESS_TIERS = {AUTHOR_TIER, ARCHITECT_TIER, ADMIN_TIER}
UNLIMITED_BOOK_TIERS = {READER_TIER, AUTHOR_TIER, ARCHITECT_TIER, ADMIN_TIER}
VALID_USER_TIERS = {FREE_TIER, READER_TIER, AUTHOR_TIER, ARCHITECT_TIER, ADMIN_TIER}
DAILY_LIMIT_MESSAGE = "Your daily limit refreshes tomorrow. Want higher limits now? Upgrade."
VALID_PAID_PLAN_CODES = {
    "reader_monthly",
    "reader_annual",
    "author_monthly",
    "author_annual",
    "architect_monthly",
    "architect_annual",
}
SUPPORTED_PADDLE_WEBHOOK_EVENTS = (
    "transaction.completed",
    "subscription.created",
    "subscription.updated",
    "subscription.canceled",
    "subscription.past_due",
    "subscription.paused",
)
PADDLE_WEBHOOK_ENDPOINT_PATH = "/api/v1/webhooks/paddle"
TRIAL_EMAIL_JOB_ENDPOINT_PATH = "/api/v1/internal/jobs/send-due-trial-emails"
TRIAL_EMAIL_RUNNER_SCRIPT = "backend/scripts/run_due_trial_emails.py"
PRIORITY_QUEUE_NAMES = (
    "extraction_priority",
    "analysis_priority",
)
PLACEHOLDER_ENV_VALUES = {
    "pdl_live_or_sandbox_key_here",
    "pdl_webhook_secret_here",
    "pri_reader_monthly",
    "pri_reader_annual",
    "pri_author_monthly",
    "pri_author_annual",
    "pri_architect_monthly",
    "pri_architect_annual",
    "replace_with_an_internal_job_secret",
    "dummy",
}

LEGACY_TIER_ALIASES = {
    "pro": AUTHOR_TIER,
    "power": ARCHITECT_TIER,
}

LEGACY_PLAN_ALIASES = {
    "pro_monthly": "reader_monthly",
    "pro_annual": "reader_annual",
    "power_monthly": "author_monthly",
    "power_annual": "author_annual",
}

PLAN_PRICES_USD = {
    "reader_monthly": 12,
    "reader_annual": 120,
    "author_monthly": 29,
    "author_annual": 290,
    "architect_monthly": 49,
    "architect_annual": 490,
}

PLAN_DISPLAY_NAMES = {
    "reader_monthly": "Reader",
    "reader_annual": "Reader",
    "author_monthly": "Author",
    "author_annual": "Author",
    "architect_monthly": "Lore Architect",
    "architect_annual": "Lore Architect",
}


@dataclass(frozen=True)
class TierPresentation:
    plan_tier: str
    access_tier: str
    tier_label: str
    trial_active: bool
    trial_ends_at: datetime | None


def normalize_tier(tier: str | None) -> str:
    cleaned = (tier or FREE_TIER).strip().lower()
    return LEGACY_TIER_ALIASES.get(cleaned, cleaned if cleaned in VALID_USER_TIERS else FREE_TIER)


def normalize_plan_code(plan: str | None) -> str:
    cleaned = (plan or "").strip().lower()
    return LEGACY_PLAN_ALIASES.get(cleaned, cleaned)


def has_meaningful_setting_value(value: str | None) -> bool:
    cleaned = (value or "").strip()
    return bool(cleaned) and cleaned.lower() not in PLACEHOLDER_ENV_VALUES


def tier_from_plan_code(plan: str | None, price_id: str = "", plan_name: str = "") -> str:
    normalized_plan = normalize_plan_code(plan)
    if normalized_plan.startswith("architect_"):
        return ARCHITECT_TIER
    if normalized_plan.startswith("author_"):
        return AUTHOR_TIER
    if normalized_plan.startswith("reader_"):
        return READER_TIER

    fallback = f"{plan_name} {price_id}".lower()
    if "architect" in fallback or "lore architect" in fallback:
        return ARCHITECT_TIER
    if "author" in fallback or "power" in fallback:
        return AUTHOR_TIER
    if "reader" in fallback or "pro" in fallback:
        return READER_TIER
    return FREE_TIER


def trial_ends_at(created_at: datetime | None) -> datetime | None:
    if created_at is None:
        return None
    created = created_at if created_at.tzinfo else created_at.replace(tzinfo=UTC)
    return created + timedelta(days=TRIAL_DAYS)


def trial_is_active(created_at: datetime | None, now: datetime | None = None) -> bool:
    ends_at = trial_ends_at(created_at)
    if ends_at is None:
        return False
    current = now or datetime.now(UTC)
    current = current if current.tzinfo else current.replace(tzinfo=UTC)
    return current < ends_at


def user_access_tier(user: Any, now: datetime | None = None) -> str:
    plan_tier = normalize_tier(getattr(user, "tier", FREE_TIER))
    if settings.DEBUG:
        return ARCHITECT_TIER
    if plan_tier in {READER_TIER, AUTHOR_TIER, ARCHITECT_TIER, ADMIN_TIER}:
        return plan_tier
    if trial_is_active(getattr(user, "created_at", None), now):
        return AUTHOR_TIER
    return FREE_TIER


def build_tier_presentation(user: Any, now: datetime | None = None) -> TierPresentation:
    plan_tier = normalize_tier(getattr(user, "tier", FREE_TIER))
    access_tier = user_access_tier(user, now)
    ends_at = trial_ends_at(getattr(user, "created_at", None))
    is_trial = not settings.DEBUG and plan_tier == FREE_TIER and access_tier == AUTHOR_TIER
    return TierPresentation(
        plan_tier=plan_tier,
        access_tier=access_tier,
        tier_label=tier_display_label(access_tier, trial_active=is_trial),
        trial_active=is_trial,
        trial_ends_at=ends_at if is_trial else None,
    )


def tier_display_label(tier: str, trial_active: bool = False) -> str:
    labels = {
        FREE_TIER: "Free",
        READER_TIER: "Reader",
        AUTHOR_TIER: "Author",
        ARCHITECT_TIER: "Lore Architect",
        ADMIN_TIER: "Admin",
    }
    label = labels.get(normalize_tier(tier), "Free")
    return f"{label} (free trial)" if trial_active else label


def user_can_author(user: Any) -> bool:
    return user_access_tier(user) in AUTHOR_ACCESS_TIERS


def require_author_access(user: Any) -> None:
    if not user_can_author(user):
        raise HTTPException(403, "This authoring feature requires an Author or Lore Architect plan.")


def price_id_for_plan(plan: str) -> str:
    normalized = normalize_plan_code(plan)
    mapping = {
        "reader_monthly": settings.PADDLE_READER_MONTHLY_PRICE_ID or settings.PADDLE_PRO_MONTHLY_PRICE_ID or "",
        "reader_annual": settings.PADDLE_READER_ANNUAL_PRICE_ID or settings.PADDLE_PRO_ANNUAL_PRICE_ID or "",
        "author_monthly": settings.PADDLE_AUTHOR_MONTHLY_PRICE_ID or settings.PADDLE_POWER_MONTHLY_PRICE_ID or "",
        "author_annual": settings.PADDLE_AUTHOR_ANNUAL_PRICE_ID or settings.PADDLE_POWER_ANNUAL_PRICE_ID or "",
        "architect_monthly": settings.PADDLE_ARCHITECT_MONTHLY_PRICE_ID or "",
        "architect_annual": settings.PADDLE_ARCHITECT_ANNUAL_PRICE_ID or "",
    }
    price_id = mapping.get(normalized, "")
    if not price_id:
        raise RuntimeError(f"Missing Paddle price mapping for plan: {normalized}")
    return price_id


def billing_interval_for_plan(plan: str) -> str:
    normalized = normalize_plan_code(plan)
    return "annual" if normalized.endswith("_annual") else "monthly"


def paddle_plan_is_configured(plan: str) -> bool:
    try:
        return has_meaningful_setting_value(settings.PADDLE_API_KEY) and has_meaningful_setting_value(price_id_for_plan(plan))
    except RuntimeError:
        return False


def any_paddle_plan_is_configured() -> bool:
    return has_meaningful_setting_value(settings.PADDLE_API_KEY) and any(
        paddle_plan_is_configured(plan) for plan in VALID_PAID_PLAN_CODES
    )


def billing_configuration_status() -> dict[str, Any]:
    plan_price_ids: dict[str, str] = {}
    plans: list[dict[str, Any]] = []
    missing_configuration: list[str] = []

    paddle_api_key_present = has_meaningful_setting_value(settings.PADDLE_API_KEY)
    webhook_secret_present = has_meaningful_setting_value(settings.PADDLE_WEBHOOK_SECRET)
    default_checkout_url_present = has_meaningful_setting_value(settings.PADDLE_DEFAULT_CHECKOUT_URL)
    resend_api_key_present = has_meaningful_setting_value(settings.RESEND_API_KEY)
    internal_job_secret_present = has_meaningful_setting_value(settings.INTERNAL_JOB_SECRET)

    if not paddle_api_key_present:
        missing_configuration.append("PADDLE_API_KEY")
    if not webhook_secret_present:
        missing_configuration.append("PADDLE_WEBHOOK_SECRET")
    if not resend_api_key_present:
        missing_configuration.append("RESEND_API_KEY")
    if not internal_job_secret_present:
        missing_configuration.append("INTERNAL_JOB_SECRET")

    for plan in sorted(VALID_PAID_PLAN_CODES):
        normalized = normalize_plan_code(plan)
        price_id = ""
        try:
            price_id = price_id_for_plan(normalized)
        except RuntimeError:
            price_id = ""

        env_key = f"PADDLE_{normalized.upper()}_PRICE_ID"
        if not has_meaningful_setting_value(price_id):
            missing_configuration.append(env_key)

        plan_price_ids[normalized] = price_id
        plans.append(
            {
                "code": normalized,
                "display_name": PLAN_DISPLAY_NAMES.get(normalized, normalized.replace("_", " ").title()),
                "billing_interval": billing_interval_for_plan(normalized),
                "price_usd": PLAN_PRICES_USD.get(normalized, 0),
                "configured": bool(paddle_api_key_present and has_meaningful_setting_value(price_id)),
                "price_id_present": has_meaningful_setting_value(price_id),
            }
        )

    fully_configured_plan_count = sum(1 for plan in plans if plan["configured"])
    external_action_items = [
        f"Register `{PADDLE_WEBHOOK_ENDPOINT_PATH}` in Paddle and subscribe it to the supported events.",
        "Run one live or sandbox checkout end to end and confirm the paid tier upgrades after the webhook lands.",
        f"Run a scheduler that calls `POST {TRIAL_EMAIL_JOB_ENDPOINT_PATH}` or invokes `{TRIAL_EMAIL_RUNNER_SCRIPT} --limit 100`.",
        "Mirror the repo's priority-queue worker commands in production so Architect priority processing matches local behavior.",
    ]
    return {
        "billing_enabled": paddle_api_key_present and fully_configured_plan_count > 0,
        "payments_ready": paddle_api_key_present and webhook_secret_present and fully_configured_plan_count == len(VALID_PAID_PLAN_CODES),
        "paddle_api_key_present": paddle_api_key_present,
        "webhook_secret_present": webhook_secret_present,
        "default_checkout_url_present": default_checkout_url_present,
        "resend_api_key_present": resend_api_key_present,
        "internal_job_secret_present": internal_job_secret_present,
        "fully_configured_plan_count": fully_configured_plan_count,
        "missing_configuration": missing_configuration,
        "plans": plans,
        "webhook_endpoint_path": PADDLE_WEBHOOK_ENDPOINT_PATH,
        "supported_webhook_events": list(SUPPORTED_PADDLE_WEBHOOK_EVENTS),
        "trial_email_job_endpoint_path": TRIAL_EMAIL_JOB_ENDPOINT_PATH,
        "trial_email_runner_script": TRIAL_EMAIL_RUNNER_SCRIPT,
        "trial_email_automation_code_ready": True,
        "priority_processing_code_ready": True,
        "priority_queue_names": list(PRIORITY_QUEUE_NAMES),
        "points_wallet_ready": True,
        "points_spend_ready": True,
        "rewarded_ads_code_ready": True,
        "external_action_items": external_action_items,
    }


def event_id_from_paddle_payload(payload: dict[str, Any]) -> str:
    return str(payload.get("event_id") or payload.get("notification_id") or payload.get("id") or "")


def paddle_plan_from_event_data(data: dict[str, Any]) -> str:
    custom_data = data.get("custom_data") or {}
    if isinstance(custom_data, dict) and custom_data.get("plan"):
        return normalize_plan_code(str(custom_data["plan"]))

    items = data.get("items") or []
    for item in items:
        price = item.get("price") or {}
        product = price.get("product") or {}
        candidate = f"{price.get('name', '')} {price.get('description', '')} {product.get('name', '')}".lower()
        interval = ((price.get("billing_cycle") or {}).get("interval") or "").lower()
        suffix = "annual" if interval == "year" else "monthly"
        if "architect" in candidate or "lore architect" in candidate:
            return f"architect_{suffix}"
        if "author" in candidate or "power" in candidate:
            return f"author_{suffix}"
        if "reader" in candidate or "pro" in candidate:
            return f"reader_{suffix}"
    return "reader_monthly"


def paddle_price_id_from_event_data(data: dict[str, Any]) -> str:
    items = data.get("items") or []
    for item in items:
        price = item.get("price") or {}
        if price.get("id"):
            return str(price["id"])
    return ""


def coerce_user_id(value: object | None) -> uuid.UUID | None:
    if value is None:
        return None
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return None


def free_search_limit_per_day(user: Any) -> int | None:
    return settings.FREE_SEARCH_PER_DAY if user_access_tier(user) == FREE_TIER else None


def prediction_limit_per_day(user: Any) -> int:
    tier = user_access_tier(user)
    return {
        FREE_TIER: settings.FREE_PREDICTION_PER_DAY,
        READER_TIER: settings.READER_PREDICTION_PER_DAY,
        AUTHOR_TIER: settings.AUTHOR_PREDICTION_PER_DAY,
        ARCHITECT_TIER: settings.ARCHITECT_PREDICTION_PER_DAY,
        ADMIN_TIER: 999999,
    }.get(tier, settings.FREE_PREDICTION_PER_DAY)


def protected_authoring_limit_per_day(user: Any) -> int:
    presentation = build_tier_presentation(user)
    tier = presentation.access_tier
    if presentation.trial_active:
        return settings.TRIAL_HIGH_COST_TURNS_PER_DAY
    return {
        FREE_TIER: 0,
        READER_TIER: 0,
        AUTHOR_TIER: settings.AUTHOR_HIGH_COST_TURNS_PER_DAY,
        ARCHITECT_TIER: settings.ARCHITECT_HIGH_COST_TURNS_PER_DAY,
        ADMIN_TIER: 999999,
    }.get(tier, 0)


def summary_mode_allowed(user: Any, mode: str) -> bool:
    tier = user_access_tier(user)
    if tier in {READER_TIER, AUTHOR_TIER, ARCHITECT_TIER, ADMIN_TIER}:
        return True
    return mode == "short"
