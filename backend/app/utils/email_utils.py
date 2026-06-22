from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.redis import (
    consume_email_unsubscribe_token,
    get_email_preferences_token_payload,
    get_redis,
    key_ratelimit,
    store_email_preferences_token,
    store_email_unsubscribe_token,
)
from app.models.user import EmailPreference, User
from app.utils.auth_utils import normalize_email
from app.utils.billing_utils import FREE_TIER, subscription_tier_for_user

EMAIL_CATEGORY_TRANSACTIONAL = "transactional"
EMAIL_CATEGORY_PRODUCT_UPDATES = "product_updates"
EMAIL_CATEGORY_MARKETING = "marketing"
EMAIL_CATEGORIES = {
    EMAIL_CATEGORY_TRANSACTIONAL,
    EMAIL_CATEGORY_PRODUCT_UPDATES,
    EMAIL_CATEGORY_MARKETING,
}
USAGE_LIMIT_UPGRADE_THRESHOLD = 3
USAGE_LIMIT_UPGRADE_COOLDOWN_SECONDS = 7 * 24 * 60 * 60


@dataclass(slots=True)
class EmailPreferenceLinks:
    unsubscribe_url: str
    preferences_url: str


def can_send_email(pref: EmailPreference | None, category: str) -> bool:
    if category == EMAIL_CATEGORY_TRANSACTIONAL:
        return True
    if pref is None:
        return True
    if pref.unsubscribed_all:
        return False
    if category == EMAIL_CATEGORY_PRODUCT_UPDATES:
        return bool(pref.product_updates)
    if category == EMAIL_CATEGORY_MARKETING:
        return bool(pref.marketing)
    return False


async def get_email_preference_by_user_id(db: AsyncSession, user_id: str) -> EmailPreference | None:
    return (
        await db.execute(select(EmailPreference).where(EmailPreference.user_id == user_id))
    ).scalar_one_or_none()


async def get_email_preference_by_email(db: AsyncSession, email: str) -> EmailPreference | None:
    normalized = normalize_email(email)
    return (
        await db.execute(
            select(EmailPreference).where(func.lower(EmailPreference.email) == normalized)
        )
    ).scalar_one_or_none()


async def get_or_create_email_preference(
    db: AsyncSession,
    *,
    user: User | None = None,
    email: str | None = None,
) -> EmailPreference:
    target_email = normalize_email(email or (user.email if user else ""))
    if not target_email:
        raise ValueError("An email address is required to manage email preferences.")

    existing = None
    if user is not None:
        existing = await get_email_preference_by_user_id(db, str(user.id))
    if existing is None:
        existing = await get_email_preference_by_email(db, target_email)

    if existing is None:
        if user is None:
            user = (
                await db.execute(select(User).where(func.lower(User.email) == target_email))
            ).scalar_one_or_none()
        if user is None:
            raise ValueError("No user found for the provided email address.")
        existing = EmailPreference(user_id=user.id, email=target_email)
        db.add(existing)
        await db.flush()

    if existing.email != target_email:
        existing.email = target_email
    if user is not None and existing.user_id != user.id:
        existing.user_id = user.id
    return existing


async def update_email_preferences(
    db: AsyncSession,
    *,
    user: User,
    product_updates: bool,
    marketing: bool,
) -> EmailPreference:
    preference = await get_or_create_email_preference(db, user=user)
    preference.email = normalize_email(user.email)
    preference.product_updates = bool(product_updates)
    preference.marketing = bool(marketing)
    preference.unsubscribed_all = not preference.product_updates and not preference.marketing
    preference.unsubscribed_at = datetime.now(UTC) if preference.unsubscribed_all else None
    await db.commit()
    await db.refresh(preference)
    return preference


async def unsubscribe_all_promotional_email(
    db: AsyncSession,
    *,
    user: User,
) -> EmailPreference:
    preference = await get_or_create_email_preference(db, user=user)
    preference.email = normalize_email(user.email)
    preference.product_updates = False
    preference.marketing = False
    preference.unsubscribed_all = True
    if preference.unsubscribed_at is None:
        preference.unsubscribed_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(preference)
    return preference


async def build_email_preference_links(user: User) -> EmailPreferenceLinks:
    normalized_email = normalize_email(user.email)
    unsubscribe_token = secrets.token_urlsafe(32)
    preferences_token = secrets.token_urlsafe(32)
    payload = {"user_id": str(user.id), "email": normalized_email}
    await store_email_unsubscribe_token(
        unsubscribe_token,
        payload,
        settings.EMAIL_UNSUBSCRIBE_TOKEN_TTL_SECONDS,
    )
    await store_email_preferences_token(
        preferences_token,
        payload,
        settings.EMAIL_PREFERENCES_TOKEN_TTL_SECONDS,
    )
    app_url = (settings.APP_URL or "https://getlorevia.com").strip().rstrip("/")
    if "://" not in app_url:
        app_url = f"https://{app_url}"
    base_api_url = f"{app_url}{settings.API_V1_PREFIX}/email"
    return EmailPreferenceLinks(
        unsubscribe_url=f"{base_api_url}/unsubscribe?token={unsubscribe_token}",
        preferences_url=f"{base_api_url}/preferences?token={preferences_token}",
    )


async def resolve_preferences_token(token: str) -> dict[str, str] | None:
    return await get_email_preferences_token_payload(token)


async def consume_unsubscribe_token(token: str) -> dict[str, str] | None:
    return await consume_email_unsubscribe_token(token)


async def track_usage_limit_friction_and_maybe_send(
    user: User,
    *,
    action: str,
) -> None:
    if not user.email or not user.email_verified_at:
        return
    if subscription_tier_for_user(user) != FREE_TIER:
        return

    current = datetime.now(UTC)
    day_bucket = current.strftime("%Y%m%d")
    midnight_tomorrow = (
        current.replace(hour=0, minute=0, second=0, microsecond=0).timestamp() + 86400
    )
    bucket_ttl = max(int(midnight_tomorrow - current.timestamp()), 1)
    hit_key = key_ratelimit(str(user.id), f"upgrade_offer_hits:{action}:{day_bucket}")
    sent_key = key_ratelimit(str(user.id), f"upgrade_offer_sent:{action}")

    r = await get_redis()
    await r.set(hit_key, "0", ex=bucket_ttl, nx=True)
    hits = int(await r.incr(hit_key))
    if hits < USAGE_LIMIT_UPGRADE_THRESHOLD:
        return
    sent = await r.set(sent_key, "1", ex=USAGE_LIMIT_UPGRADE_COOLDOWN_SECONDS, nx=True)
    if not sent:
        return

    from app.services.email_service import send_usage_limit_upgrade_offer_email

    focus_labels = {
        "search": "search",
        "prediction": "question and answer",
        "high_cost_authoring": "authoring and advisory",
    }
    await send_usage_limit_upgrade_offer_email(
        user.email,
        focus_area=focus_labels.get(action, "workflow"),
    )
