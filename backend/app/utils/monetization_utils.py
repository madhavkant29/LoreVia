from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

TRIAL_EMAIL_STARTED = "trial_started"
TRIAL_EMAIL_NUDGE = "trial_nudge"
TRIAL_EMAIL_ENDING = "trial_ending"
TRIAL_EMAIL_ENDED = "trial_ended"
TRIAL_EMAIL_TYPES = {
    TRIAL_EMAIL_STARTED,
    TRIAL_EMAIL_NUDGE,
    TRIAL_EMAIL_ENDING,
    TRIAL_EMAIL_ENDED,
}

POINT_SOURCE_REFERRAL = "referral_reward"
POINT_SOURCE_FIRST_BOOK = "first_processed_book"
POINT_SOURCE_REWARDED_AD = "rewarded_ad"
POINT_SOURCE_DAILY_LOGIN = "daily_login"
POINT_SOURCE_PUBLIC_SHARE = "public_share"
POINT_SOURCE_REVIEW_FEEDBACK = "review_feedback"
POINT_SOURCE_BETA_READ_AUTHOR_REWARD = "beta_read_positive_review"
POINT_ENTRY_GRANT = "grant"
POINT_ENTRY_EXPIRE = "expire"
POINT_ENTRY_SPEND = "spend"

POINT_ACTION_SEARCH = "search"
POINT_ACTION_PREDICTION = "prediction"
POINT_ACTION_HIGH_COST = "high_cost_authoring"

POINT_OFFER_SEARCH_PACK = "search_pack_5"
POINT_OFFER_PREDICTION_OVERFLOW = "prediction_overflow_1"
POINT_OFFER_HIGH_COST_OVERFLOW = "high_cost_overflow_1"

POINT_SOURCE_OVERFLOW_SEARCH = "overflow_search"
POINT_SOURCE_OVERFLOW_PREDICTION = "overflow_prediction"
POINT_SOURCE_OVERFLOW_HIGH_COST = "overflow_high_cost_authoring"

REFERRAL_REWARD_POINTS = 50
REFERRED_REWARD_POINTS = 25
FIRST_PROCESSED_BOOK_POINTS = 25
POINT_EXPIRY_DAYS = 90

REWARDED_AD_PROVIDER_GPT = "google_publisher_tag"
REWARDED_AD_STATUS_PENDING = "pending"
REWARDED_AD_STATUS_REWARDED = "rewarded"
REWARDED_AD_STATUS_DISMISSED = "dismissed"
REWARDED_AD_STATUS_UNSUPPORTED = "unsupported"
REWARDED_AD_STATUS_ERROR = "error"
REWARDED_AD_STATUS_EXPIRED = "expired"
REWARDED_AD_FINAL_STATUSES = {
    REWARDED_AD_STATUS_REWARDED,
    REWARDED_AD_STATUS_DISMISSED,
    REWARDED_AD_STATUS_UNSUPPORTED,
    REWARDED_AD_STATUS_ERROR,
    REWARDED_AD_STATUS_EXPIRED,
}

_CODE_CHARS = re.compile(r"[^A-Z0-9]")


@dataclass(frozen=True)
class PointSpendOffer:
    code: str
    action: str
    source_type: str
    title: str
    description: str
    points_cost: int
    units: int
    requires_existing_access: bool = False


POINT_SPEND_OFFERS: tuple[PointSpendOffer, ...] = (
    PointSpendOffer(
        code=POINT_OFFER_SEARCH_PACK,
        action=POINT_ACTION_SEARCH,
        source_type=POINT_SOURCE_OVERFLOW_SEARCH,
        title="5 extra semantic searches today",
        description="Small overflow relief for Free readers who hit the daily search cap.",
        points_cost=3,
        units=5,
    ),
    PointSpendOffer(
        code=POINT_OFFER_PREDICTION_OVERFLOW,
        action=POINT_ACTION_PREDICTION,
        source_type=POINT_SOURCE_OVERFLOW_PREDICTION,
        title="1 extra prediction query today",
        description="One more grounded Q&A turn after you hit today's prediction limit.",
        points_cost=6,
        units=1,
    ),
    PointSpendOffer(
        code=POINT_OFFER_HIGH_COST_OVERFLOW,
        action=POINT_ACTION_HIGH_COST,
        source_type=POINT_SOURCE_OVERFLOW_HIGH_COST,
        title="1 extra Story Advisor or continuity turn today",
        description="Same-tier overflow only. This never unlocks author tools for lower plans.",
        points_cost=10,
        units=1,
        requires_existing_access=True,
    ),
)


def utc_now() -> datetime:
    return datetime.now(UTC)


def utc_day_bounds(now: datetime | None = None) -> tuple[datetime, datetime]:
    current = now or utc_now()
    current = current if current.tzinfo else current.replace(tzinfo=UTC)
    start = current.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)


def normalize_referral_code(value: str | None) -> str:
    return _CODE_CHARS.sub("", (value or "").strip().upper())


def generate_referral_code(user: Any) -> str:
    username = normalize_referral_code(getattr(user, "username", None) or "")
    prefix = username[:8] if len(username) >= 3 else "LORE"
    token = uuid.uuid4().hex[:8].upper()
    return f"{prefix}{token}"


def points_expire_at(now: datetime | None = None) -> datetime:
    current = now or utc_now()
    current = current if current.tzinfo else current.replace(tzinfo=UTC)
    return current + timedelta(days=POINT_EXPIRY_DAYS)


def build_trial_email_schedule(started_at: datetime | None, now: datetime | None = None) -> dict[str, datetime]:
    base = started_at or now or utc_now()
    base = base if base.tzinfo else base.replace(tzinfo=UTC)
    return {
        TRIAL_EMAIL_STARTED: base,
        TRIAL_EMAIL_NUDGE: base + timedelta(days=3),
        TRIAL_EMAIL_ENDING: base + timedelta(days=9),
        TRIAL_EMAIL_ENDED: base + timedelta(days=10),
    }


def points_balance_from_deltas(deltas: list[int]) -> int:
    return max(sum(deltas), 0)


def point_spend_offer_by_code(code: str | None) -> PointSpendOffer | None:
    normalized = (code or "").strip().lower()
    for offer in POINT_SPEND_OFFERS:
        if offer.code == normalized:
            return offer
    return None


def point_spend_offer_for_action(action: str | None) -> PointSpendOffer | None:
    normalized = (action or "").strip().lower()
    for offer in POINT_SPEND_OFFERS:
        if offer.action == normalized:
            return offer
    return None


def normalize_rewarded_ad_outcome(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    if normalized == REWARDED_AD_STATUS_REWARDED:
        return REWARDED_AD_STATUS_REWARDED
    if normalized == REWARDED_AD_STATUS_DISMISSED:
        return REWARDED_AD_STATUS_DISMISSED
    if normalized == REWARDED_AD_STATUS_UNSUPPORTED:
        return REWARDED_AD_STATUS_UNSUPPORTED
    if normalized == REWARDED_AD_STATUS_ERROR:
        return REWARDED_AD_STATUS_ERROR
    return REWARDED_AD_STATUS_ERROR
