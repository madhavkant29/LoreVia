from __future__ import annotations

import json
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import jwt
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.redis import consume_billing_confirmation_token
from app.models.book import Book, BookUploadCharge, SeriesBook
from app.models.intelligence import WorldBuildingDocument
from app.models.user import SubscriptionEvent, User

# Subscription tiers describe product entitlements on the user account.
# They must not be used as collaboration roles or per-book permissions.
# Book access is derived separately from ownership or BookCollaborator.role.
FREE_TIER = "free"
AUTHOR_TIER = "author"
ARCHITECT_TIER = "architect"

TRIAL_DAYS = 10
VALID_USER_TIERS = {FREE_TIER, AUTHOR_TIER, ARCHITECT_TIER}
PAID_READING_TIERS = {AUTHOR_TIER, ARCHITECT_TIER}
AUTHORING_SUBSCRIPTION_TIERS = {AUTHOR_TIER, ARCHITECT_TIER}
UNLIMITED_OWNER_UPLOAD_TIERS = {ARCHITECT_TIER}
DAILY_LIMIT_MESSAGE = "Your daily limit refreshes tomorrow. Want higher limits now? Upgrade."
SUPPORTED_PADDLE_WEBHOOK_EVENTS = (
    "adjustment.created",
    "adjustment.updated",
    "transaction.completed",
    "transaction.past_due",
    "transaction.payment_failed",
    "transaction.updated",
    "subscription.activated",
    "subscription.canceled",
    "subscription.created",
    "subscription.past_due",
    "subscription.paused",
    "subscription.resumed",
    "subscription.trialing",
    "subscription.updated",
)
PADDLE_WEBHOOK_ENDPOINT_PATH = "/api/v1/webhooks/paddle"
TRIAL_EMAIL_JOB_ENDPOINT_PATH = "/api/v1/internal/jobs/send-due-trial-emails"
TRIAL_EMAIL_RUNNER_SCRIPT = "backend/scripts/run_due_trial_emails.py"
PRIORITY_QUEUE_NAMES = (
    "extraction_priority",
    "analysis_priority",
)
BILLING_CONFIRMATION_TOKEN_TYPE = "billing_confirmation"
BILLING_CONFIRMATION_TOKEN_TTL_SECONDS = 3600
BILLING_CONFIRMATION_QUERY_KEY = "lvct"
PLACEHOLDER_ENV_VALUES = {
    "pdl_live_or_sandbox_key_here",
    "pdl_webhook_secret_here",
    "price_author_monthly_here",
    "price_author_annual_here",
    "price_architect_monthly_here",
    "price_architect_annual_here",
    "replace_with_an_internal_job_secret",
    "dummy",
}

LEGACY_TIER_ALIASES = {
    "collaborator": FREE_TIER,
    "reader": FREE_TIER,
    "pro": AUTHOR_TIER,
    "power": ARCHITECT_TIER,
}

LEGACY_PLAN_ALIASES = {
    "pro_monthly": "author_monthly",
    "pro_annual": "author_annual",
    "power_monthly": "architect_monthly",
    "power_annual": "architect_annual",
}

APP_ROOT = Path(__file__).resolve().parents[1]
BACKEND_PRICING_CATALOG_PATH = APP_ROOT / "data" / "pricing-catalog.json"
SHARED_PRICING_CATALOG_PATH = BACKEND_PRICING_CATALOG_PATH


@lru_cache(maxsize=1)
def load_shared_pricing_catalog() -> dict[str, list[dict[str, Any]]]:
    return json.loads(SHARED_PRICING_CATALOG_PATH.read_text(encoding="utf-8"))


def _catalog_plans() -> list[dict[str, Any]]:
    plans = load_shared_pricing_catalog().get("plans", [])
    if not isinstance(plans, list):
        raise ValueError("Shared pricing catalog is missing a valid plans list.")
    return plans


PLAN_METADATA_BY_CODE = {str(plan["code"]): plan for plan in _catalog_plans()}
PLAN_PRICES_USD = {code: int(plan["price_usd"]) for code, plan in PLAN_METADATA_BY_CODE.items()}
PLAN_DISPLAY_NAMES = {
    code: str(plan["display_name"]) for code, plan in PLAN_METADATA_BY_CODE.items()
}
PLAN_INTERVALS = {
    code: str(plan["billing_interval"]) for code, plan in PLAN_METADATA_BY_CODE.items()
}
PLAN_PRICE_ID_ENV_KEYS = {
    code: [str(env_key) for env_key in plan.get("price_id_env_keys", [])]
    for code, plan in PLAN_METADATA_BY_CODE.items()
}
VALID_PAID_PLAN_CODES = {
    code for code, plan in PLAN_METADATA_BY_CODE.items() if bool(plan.get("checkout_enabled"))
}


@dataclass(frozen=True)
class TierPresentation:
    plan_tier: str
    access_tier: str
    tier_label: str
    trial_active: bool
    trial_ends_at: datetime | None


@dataclass(frozen=True)
class UploadUsageSummary:
    manuscript_uploads: int
    worldbuilding_uploads: int
    total_uploads: int
    upload_limit: int | None
    uploads_remaining: int | None
    upload_limit_unlimited: bool


@dataclass(frozen=True)
class SubscriptionMetricsSummary:
    cohort_start: date
    cohort_end: date
    trial_starts: int
    trial_to_paid_conversions: int
    trial_to_paid_rate: float | None
    cancellation_events: int
    resolved_cancellation_events: int
    unresolved_cancellation_events: int
    reactivated_after_cancellation: int
    churned_after_cancellation: int
    post_cancel_churn_rate: float | None
    reactivation_window_days: int


def normalize_tier(tier: str | None) -> str:
    cleaned = (tier or FREE_TIER).strip().lower()
    return LEGACY_TIER_ALIASES.get(cleaned, cleaned if cleaned in VALID_USER_TIERS else FREE_TIER)


def normalize_plan_code(plan: str | None) -> str:
    cleaned = (plan or "").strip().lower()
    return LEGACY_PLAN_ALIASES.get(cleaned, cleaned)


def has_meaningful_setting_value(value: str | None) -> bool:
    cleaned = (value or "").strip()
    return bool(cleaned) and cleaned.lower() not in PLACEHOLDER_ENV_VALUES


def recommended_paddle_default_checkout_url() -> str:
    default_app_url = "http://localhost:3000" if settings.DEBUG else "https://getlorevia.com"
    raw_app_url = (settings.APP_URL or "").strip() or default_app_url
    if "://" not in raw_app_url:
        raw_app_url = f"https://{raw_app_url.lstrip('/')}"
    parts = urlsplit(raw_app_url)
    if not settings.DEBUG and parts.hostname in {"localhost", "127.0.0.1", "0.0.0.0"}:
        raw_app_url = default_app_url
    return f"{raw_app_url.rstrip('/')}/checkout"


def create_billing_confirmation_token(transaction_id: str) -> str:
    normalized_transaction_id = transaction_id.strip()
    expire = datetime.now(UTC) + timedelta(seconds=BILLING_CONFIRMATION_TOKEN_TTL_SECONDS)
    return jwt.encode(
        {
            "txn": normalized_transaction_id,
            "jti": secrets.token_urlsafe(24),
            "exp": expire,
            "type": BILLING_CONFIRMATION_TOKEN_TYPE,
        },
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )


def _decode_billing_confirmation_token(
    token: str | None, transaction_id: str
) -> dict[str, Any] | None:
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
    if (
        str(payload.get("type") or "") == BILLING_CONFIRMATION_TOKEN_TYPE
        and str(payload.get("txn") or "").strip() == transaction_id.strip()
        and str(payload.get("jti") or "").strip()
    ):
        return payload
    return None


def verify_billing_confirmation_token(token: str | None, transaction_id: str) -> bool:
    return _decode_billing_confirmation_token(token, transaction_id) is not None


async def consume_billing_confirmation_token_once(token: str | None, transaction_id: str) -> bool:
    payload = _decode_billing_confirmation_token(token, transaction_id)
    if payload is None:
        return False
    ttl_seconds = int(payload.get("exp") or 0) - int(datetime.now(UTC).timestamp())
    if ttl_seconds <= 0:
        return False
    return await consume_billing_confirmation_token(str(payload["jti"]), ttl_seconds)


def append_billing_confirmation_token(checkout_url: str, confirmation_token: str) -> str:
    parts = urlsplit(checkout_url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query[BILLING_CONFIRMATION_QUERY_KEY] = confirmation_token
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def tier_from_plan_code(plan: str | None, price_id: str = "", plan_name: str = "") -> str:
    normalized_plan = normalize_plan_code(plan)
    if normalized_plan.startswith("architect_"):
        return ARCHITECT_TIER
    if normalized_plan.startswith("author_"):
        return AUTHOR_TIER
    if normalized_plan.startswith("reader_"):
        return FREE_TIER

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


def subscription_tier_for_user(user: Any) -> str:
    return normalize_tier(getattr(user, "tier", FREE_TIER))


def billing_access_tier(user: Any, now: datetime | None = None) -> str:
    plan_tier = subscription_tier_for_user(user)
    if settings.DEBUG:
        return ARCHITECT_TIER
    if plan_tier in PAID_READING_TIERS:
        return plan_tier
    if trial_is_active(getattr(user, "created_at", None), now):
        return AUTHOR_TIER
    return FREE_TIER


def user_access_tier(user: Any, now: datetime | None = None) -> str:
    return billing_access_tier(user, now)


def has_paid_reading_access(user: Any, now: datetime | None = None) -> bool:
    return billing_access_tier(user, now) in PAID_READING_TIERS


def has_authoring_access(user: Any, now: datetime | None = None) -> bool:
    return billing_access_tier(user, now) in AUTHORING_SUBSCRIPTION_TIERS


def build_tier_presentation(user: Any, now: datetime | None = None) -> TierPresentation:
    plan_tier = subscription_tier_for_user(user)
    access_tier = billing_access_tier(user, now)
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
        AUTHOR_TIER: "Author",
        ARCHITECT_TIER: "Architect",
    }
    label = labels.get(normalize_tier(tier), "Free")
    return f"{label} (free trial)" if trial_active else label


def user_can_author(user: Any) -> bool:
    return has_authoring_access(user)


def require_author_access(user: Any) -> None:
    if not user_can_author(user):
        raise HTTPException(403, "This authoring feature requires an Author or Architect plan.")


def upload_limit_for_user(user: Any) -> int | None:
    tier = billing_access_tier(user)
    if tier in UNLIMITED_OWNER_UPLOAD_TIERS:
        return None
    if tier == AUTHOR_TIER:
        return settings.AUTHOR_MAX_UPLOADS
    return 0


async def _worldbuilding_upload_cost_by_book(
    db: AsyncSession, user_id: uuid.UUID
) -> dict[uuid.UUID, int]:
    owned_book_rows = (
        await db.execute(select(Book.id, Book.primary_series_id).where(Book.user_id == user_id))
    ).all()
    if not owned_book_rows:
        return {}

    book_ids = [book_id for book_id, _primary_series_id in owned_book_rows]
    membership_rows = (
        await db.execute(
            select(SeriesBook.series_id, SeriesBook.book_id).where(SeriesBook.book_id.in_(book_ids))
        )
    ).all()

    book_to_series_ids: dict[uuid.UUID, set[uuid.UUID]] = {book_id: set() for book_id in book_ids}
    series_to_book_ids: dict[uuid.UUID, set[uuid.UUID]] = {}

    for series_id, book_id in membership_rows:
        book_to_series_ids.setdefault(book_id, set()).add(series_id)
        series_to_book_ids.setdefault(series_id, set()).add(book_id)

    for book_id, primary_series_id in owned_book_rows:
        if primary_series_id is None:
            continue
        book_to_series_ids.setdefault(book_id, set()).add(primary_series_id)
        series_to_book_ids.setdefault(primary_series_id, set()).add(book_id)

    return {
        book_id: max(
            1,
            len(
                {
                    linked_book_id
                    for series_id in linked_series_ids
                    for linked_book_id in series_to_book_ids.get(series_id, {book_id})
                }
            )
            if linked_series_ids
            else 1,
        )
        for book_id, linked_series_ids in book_to_series_ids.items()
    }


async def worldbuilding_upload_cost_for_book(db: AsyncSession, book: Any) -> int:
    cost_map = await _worldbuilding_upload_cost_by_book(db, getattr(book, "user_id"))
    return max(1, cost_map.get(getattr(book, "id"), 1))


async def calculate_upload_usage_summary(db: AsyncSession, user: Any) -> UploadUsageSummary:
    user_id = getattr(user, "id")
    base_manuscript_uploads = int(
        (await db.execute(select(func.count(Book.id)).where(Book.user_id == user_id))).scalar() or 0
    )
    extra_manuscript_uploads = int(
        (
            await db.execute(
                select(func.coalesce(func.sum(BookUploadCharge.quantity), 0)).where(
                    BookUploadCharge.user_id == user_id
                )
            )
        ).scalar()
        or 0
    )
    manuscript_uploads = base_manuscript_uploads + extra_manuscript_uploads
    upload_limit = upload_limit_for_user(user)

    worldbuilding_rows = (
        await db.execute(
            select(WorldBuildingDocument.book_id, func.count(WorldBuildingDocument.id))
            .join(Book, Book.id == WorldBuildingDocument.book_id)
            .where(
                Book.user_id == user_id,
                WorldBuildingDocument.is_active.is_(True),
            )
            .group_by(WorldBuildingDocument.book_id)
        )
    ).all()
    worldbuilding_costs = await _worldbuilding_upload_cost_by_book(db, user_id)
    worldbuilding_uploads = sum(
        int(document_count) * max(1, worldbuilding_costs.get(book_id, 1))
        for book_id, document_count in worldbuilding_rows
    )
    total_uploads = manuscript_uploads + worldbuilding_uploads
    upload_limit_unlimited = upload_limit is None
    uploads_remaining = None if upload_limit is None else max(upload_limit - total_uploads, 0)
    return UploadUsageSummary(
        manuscript_uploads=manuscript_uploads,
        worldbuilding_uploads=worldbuilding_uploads,
        total_uploads=total_uploads,
        upload_limit=upload_limit,
        uploads_remaining=uploads_remaining,
        upload_limit_unlimited=upload_limit_unlimited,
    )


async def record_book_upload_charge(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    book_id: uuid.UUID,
    charge_kind: str,
    source_id: str,
    quantity: int = 1,
    metadata: dict[str, Any] | None = None,
) -> BookUploadCharge:
    normalized_kind = " ".join(str(charge_kind or "").split()).strip()
    normalized_source_id = " ".join(str(source_id or "").split()).strip()
    if not normalized_kind:
        raise ValueError("charge_kind_required")
    if not normalized_source_id:
        raise ValueError("source_id_required")

    existing = (
        await db.execute(
            select(BookUploadCharge).where(
                BookUploadCharge.user_id == user_id,
                BookUploadCharge.charge_kind == normalized_kind,
                BookUploadCharge.source_id == normalized_source_id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    charge = BookUploadCharge(
        user_id=user_id,
        book_id=book_id,
        charge_kind=normalized_kind,
        quantity=max(1, int(quantity or 1)),
        source_id=normalized_source_id,
        metadata_json=metadata or {},
    )
    try:
        async with db.begin_nested():
            db.add(charge)
            await db.flush()
        return charge
    except IntegrityError:
        existing_after_race = (
            await db.execute(
                select(BookUploadCharge).where(
                    BookUploadCharge.user_id == user_id,
                    BookUploadCharge.charge_kind == normalized_kind,
                    BookUploadCharge.source_id == normalized_source_id,
                )
            )
        ).scalar_one_or_none()
        if existing_after_race is None:
            raise
        return existing_after_race


async def ensure_upload_capacity(
    db: AsyncSession,
    user: Any,
    *,
    requested_uploads: int,
    released_uploads: int = 0,
    context: str | None = None,
) -> UploadUsageSummary:
    summary = await calculate_upload_usage_summary(db, user)
    if summary.upload_limit is None:
        return summary

    projected_total = max(summary.total_uploads - max(released_uploads, 0), 0) + max(
        requested_uploads, 0
    )
    if projected_total <= summary.upload_limit:
        return summary

    tier = billing_access_tier(user)
    if tier == AUTHOR_TIER:
        base_message = (
            f"Author tier includes {summary.upload_limit} uploads. "
            f"You have {summary.uploads_remaining or 0} remaining. "
            "Worldbuilding manuscripts count as uploads too, and series-linked worldbuilding manuscripts count once per book in the series. "
            "Upgrade to Architect for higher active-word, processing, and storage allowances."
        )
    else:
        base_message = (
            f"This account is limited to {summary.upload_limit} owned upload"
            f"{'' if summary.upload_limit == 1 else 's'}. "
            "Worldbuilding manuscripts count as uploads too. Upgrade to Author for higher owner upload limits."
        )
    if context:
        base_message = f"{base_message} {context}"
    raise HTTPException(403, base_message)


def price_id_for_plan(plan: str) -> str:
    normalized = normalize_plan_code(plan)
    env_keys = PLAN_PRICE_ID_ENV_KEYS.get(normalized, [])
    if not env_keys:
        raise RuntimeError(f"Missing Paddle price mapping for plan: {normalized}")

    for env_key in env_keys:
        price_id = getattr(settings, env_key, None)
        if price_id:
            return str(price_id)

    raise RuntimeError(f"Missing Paddle price mapping for plan: {normalized}")


def billing_interval_for_plan(plan: str) -> str:
    normalized = normalize_plan_code(plan)
    interval = PLAN_INTERVALS.get(normalized)
    if interval in {"monthly", "annual"}:
        return interval
    return "annual" if normalized.endswith("_annual") else "monthly"


def paddle_plan_is_configured(plan: str) -> bool:
    try:
        return has_meaningful_setting_value(
            settings.PADDLE_API_KEY
        ) and has_meaningful_setting_value(price_id_for_plan(plan))
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
    default_checkout_url_present = has_meaningful_setting_value(
        settings.PADDLE_DEFAULT_CHECKOUT_URL
    )
    resend_api_key_present = has_meaningful_setting_value(settings.RESEND_API_KEY)
    internal_job_secret_present = has_meaningful_setting_value(settings.INTERNAL_JOB_SECRET)

    if not paddle_api_key_present:
        missing_configuration.append("PADDLE_API_KEY")
    if not webhook_secret_present:
        missing_configuration.append("PADDLE_WEBHOOK_SECRET")
    if not default_checkout_url_present:
        missing_configuration.append("PADDLE_DEFAULT_CHECKOUT_URL")
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

        if not has_meaningful_setting_value(price_id):
            missing_configuration.extend(PLAN_PRICE_ID_ENV_KEYS.get(normalized, []))

        plan_price_ids[normalized] = price_id
        plans.append(
            {
                "code": normalized,
                "display_name": PLAN_DISPLAY_NAMES.get(
                    normalized, normalized.replace("_", " ").title()
                ),
                "billing_interval": billing_interval_for_plan(normalized),
                "price_usd": PLAN_PRICES_USD.get(normalized, 0),
                "configured": bool(
                    paddle_api_key_present and has_meaningful_setting_value(price_id)
                ),
                "price_id_present": has_meaningful_setting_value(price_id),
            }
        )

    fully_configured_plan_count = sum(1 for plan in plans if plan["configured"])
    external_action_items = [
        f"Set Paddle > Checkout > Default payment link to `{recommended_paddle_default_checkout_url()}` and get that domain approved in the live workspace.",
        f"Register `{PADDLE_WEBHOOK_ENDPOINT_PATH}` in Paddle and subscribe it to the supported events.",
        "Run one live or sandbox checkout end to end and confirm the paid tier upgrades after the webhook lands.",
        f"Run a scheduler that calls `POST {TRIAL_EMAIL_JOB_ENDPOINT_PATH}` or invokes `{TRIAL_EMAIL_RUNNER_SCRIPT} --limit 100`.",
        "Mirror the repo's priority-queue worker commands in production so Architect priority processing matches local behavior.",
    ]
    return {
        "billing_enabled": paddle_api_key_present and fully_configured_plan_count > 0,
        "payments_ready": (
            paddle_api_key_present
            and webhook_secret_present
            and default_checkout_url_present
            and fully_configured_plan_count == len(VALID_PAID_PLAN_CODES)
        ),
        "paddle_api_key_present": paddle_api_key_present,
        "webhook_secret_present": webhook_secret_present,
        "default_checkout_url_present": default_checkout_url_present,
        "recommended_default_checkout_url": recommended_paddle_default_checkout_url(),
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
        "external_action_items": external_action_items,
    }


def event_id_from_paddle_payload(payload: dict[str, Any]) -> str:
    return str(payload.get("event_id") or payload.get("notification_id") or payload.get("id") or "")


def subscription_service_is_active(event_type: str, status: str | None) -> bool:
    normalized_status = (status or "").strip().lower()
    if event_type == "transaction.completed":
        return normalized_status in {"active", "trialing"}
    if event_type in {"subscription.activated", "subscription.resumed", "subscription.trialing"}:
        return True
    return normalized_status in {"active", "trialing"}


def subscription_event_type_for_metrics(event_type: str, status: str | None) -> str | None:
    if event_type in {
        "transaction.completed",
        "subscription.activated",
        "subscription.resumed",
        "subscription.trialing",
    }:
        return (
            "subscription_activated" if subscription_service_is_active(event_type, status) else None
        )
    if event_type in {"subscription.created", "subscription.updated"}:
        return (
            "subscription_activated" if subscription_service_is_active(event_type, status) else None
        )
    if event_type == "subscription.canceled":
        return "subscription_canceled"
    if event_type == "subscription.paused":
        return "subscription_paused"
    if event_type == "subscription.past_due":
        return "subscription_past_due"
    return None


def _cohort_bounds(
    cohort_start: date | datetime,
    cohort_end: date | datetime,
) -> tuple[date, date, datetime, datetime]:
    start_date = cohort_start.date() if isinstance(cohort_start, datetime) else cohort_start
    end_date = cohort_end.date() if isinstance(cohort_end, datetime) else cohort_end
    if end_date < start_date:
        raise ValueError("cohort_end must be on or after cohort_start")
    start_at = datetime.combine(start_date, time.min, tzinfo=UTC)
    end_at = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=UTC)
    return start_date, end_date, start_at, end_at


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round((numerator / denominator) * 100, 2)


async def record_subscription_event(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    event_type: str,
    source_event_id: str | None,
    plan: str | None = None,
    status: str | None = None,
    paddle_customer_id: str | None = None,
    paddle_sub_id: str | None = None,
    occurred_at: datetime | None = None,
    metadata: dict[str, Any] | None = None,
    source: str = "paddle",
) -> SubscriptionEvent:
    event = SubscriptionEvent(
        user_id=user_id,
        event_type=event_type,
        source=source,
        source_event_id=(source_event_id or None),
        plan=plan,
        status=status,
        paddle_customer_id=paddle_customer_id,
        paddle_sub_id=paddle_sub_id,
        metadata_json=metadata or {},
        occurred_at=(occurred_at or datetime.now(UTC)),
    )
    db.add(event)
    return event


async def build_subscription_metrics_summary(
    db: AsyncSession,
    *,
    cohort_start: date | datetime,
    cohort_end: date | datetime,
    reactivation_window_days: int = 30,
    now: datetime | None = None,
) -> SubscriptionMetricsSummary:
    start_date, end_date, start_at, end_at = _cohort_bounds(cohort_start, cohort_end)
    current = (now or datetime.now(UTC)).astimezone(UTC)
    window = timedelta(days=max(int(reactivation_window_days or 0), 1))

    cohort_users = (
        (
            await db.execute(
                select(User.id).where(User.created_at >= start_at, User.created_at < end_at)
            )
        )
        .scalars()
        .all()
    )
    cohort_user_ids = {user_id for user_id in cohort_users}

    trial_to_paid_conversions = 0
    if cohort_user_ids:
        trial_to_paid_conversions = len(
            {
                user_id
                for user_id in (
                    await db.execute(
                        select(SubscriptionEvent.user_id).where(
                            SubscriptionEvent.user_id.in_(cohort_user_ids),
                            SubscriptionEvent.event_type == "subscription_activated",
                        )
                    )
                )
                .scalars()
                .all()
            }
        )

    cancellation_events = (
        (
            await db.execute(
                select(SubscriptionEvent)
                .where(
                    SubscriptionEvent.event_type == "subscription_canceled",
                    SubscriptionEvent.occurred_at >= start_at,
                    SubscriptionEvent.occurred_at < end_at,
                )
                .order_by(SubscriptionEvent.occurred_at.asc())
            )
        )
        .scalars()
        .all()
    )

    if cancellation_events:
        cancellation_user_ids = {event.user_id for event in cancellation_events}
        reactivation_events = (
            (
                await db.execute(
                    select(SubscriptionEvent)
                    .where(
                        SubscriptionEvent.user_id.in_(cancellation_user_ids),
                        SubscriptionEvent.event_type == "subscription_activated",
                    )
                    .order_by(SubscriptionEvent.occurred_at.asc())
                )
            )
            .scalars()
            .all()
        )
    else:
        reactivation_events = []

    reactivations_by_user: dict[uuid.UUID, list[SubscriptionEvent]] = {}
    for event in reactivation_events:
        reactivations_by_user.setdefault(event.user_id, []).append(event)

    resolved_cancellation_events = 0
    unresolved_cancellation_events = 0
    reactivated_after_cancellation = 0
    churned_after_cancellation = 0

    for cancellation in cancellation_events:
        resolution_deadline = cancellation.occurred_at + window
        if resolution_deadline > current:
            unresolved_cancellation_events += 1
            continue

        resolved_cancellation_events += 1
        reactivated = any(
            candidate.occurred_at > cancellation.occurred_at
            and candidate.occurred_at <= resolution_deadline
            for candidate in reactivations_by_user.get(cancellation.user_id, [])
        )
        if reactivated:
            reactivated_after_cancellation += 1
        else:
            churned_after_cancellation += 1

    return SubscriptionMetricsSummary(
        cohort_start=start_date,
        cohort_end=end_date,
        trial_starts=len(cohort_user_ids),
        trial_to_paid_conversions=trial_to_paid_conversions,
        trial_to_paid_rate=_rate(trial_to_paid_conversions, len(cohort_user_ids)),
        cancellation_events=len(cancellation_events),
        resolved_cancellation_events=resolved_cancellation_events,
        unresolved_cancellation_events=unresolved_cancellation_events,
        reactivated_after_cancellation=reactivated_after_cancellation,
        churned_after_cancellation=churned_after_cancellation,
        post_cancel_churn_rate=_rate(churned_after_cancellation, resolved_cancellation_events),
        reactivation_window_days=window.days,
    )


def paddle_plan_from_event_data(data: dict[str, Any]) -> str:
    price_id = paddle_price_id_from_event_data(data).strip()
    if price_id:
        for plan_code, env_keys in PLAN_PRICE_ID_ENV_KEYS.items():
            if any(
                str(getattr(settings, env_key, "") or "").strip() == price_id
                for env_key in env_keys
            ):
                return normalize_plan_code(plan_code)

    items = data.get("items") or []
    for item in items:
        price = item.get("price") or {}
        product = price.get("product") or {}
        candidate = f"{price.get('name', '')} {price.get('description', '')} {product.get('name', '')}".lower()
        interval = ((price.get("billing_cycle") or {}).get("interval") or "").lower()
        suffix = "annual" if interval == "year" else "monthly"
        if "architect" in candidate or "lore architect" in candidate or "power" in candidate:
            return f"architect_{suffix}"
        if "author" in candidate or "pro" in candidate:
            return f"author_{suffix}"
        if "reader" in candidate:
            return f"reader_{suffix}"
    return ""


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
        AUTHOR_TIER: settings.AUTHOR_PREDICTION_PER_DAY,
        ARCHITECT_TIER: settings.ARCHITECT_PREDICTION_PER_DAY,
    }.get(tier, settings.FREE_PREDICTION_PER_DAY)


def protected_authoring_limit_per_day(user: Any) -> int:
    presentation = build_tier_presentation(user)
    tier = presentation.access_tier
    if presentation.trial_active:
        return settings.TRIAL_HIGH_COST_TURNS_PER_DAY
    return {
        FREE_TIER: 0,
        AUTHOR_TIER: settings.AUTHOR_HIGH_COST_TURNS_PER_DAY,
        ARCHITECT_TIER: settings.ARCHITECT_HIGH_COST_TURNS_PER_DAY,
    }.get(tier, 0)


def free_advisor_limit_per_week(user: Any) -> int | None:
    presentation = build_tier_presentation(user)
    if presentation.trial_active or presentation.access_tier != FREE_TIER:
        return None
    return settings.FREE_ADVISOR_PER_WEEK


def recall_limit_per_day(user: Any) -> int | None:
    return settings.FREE_RECALL_PER_DAY if user_access_tier(user) == FREE_TIER else None


def continuity_limit_per_day(user: Any) -> int:
    presentation = build_tier_presentation(user)
    if presentation.trial_active:
        return settings.TRIAL_HIGH_COST_TURNS_PER_DAY

    return {
        FREE_TIER: 0,
        AUTHOR_TIER: settings.AUTHOR_HIGH_COST_TURNS_PER_DAY,
        ARCHITECT_TIER: settings.ARCHITECT_HIGH_COST_TURNS_PER_DAY,
    }.get(presentation.access_tier, 0)


def summary_mode_allowed(user: Any, mode: str) -> bool:
    if mode == "short":
        return True
    if mode not in {"detailed", "key_points"}:
        return False

    raw_tier = (getattr(user, "tier", "") or "").strip().lower()
    if raw_tier == "reader":
        return True

    return has_paid_reading_access(user)
