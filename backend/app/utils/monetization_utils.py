from __future__ import annotations

import re
import uuid
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
POINT_ENTRY_GRANT = "grant"
POINT_ENTRY_EXPIRE = "expire"

REFERRAL_REWARD_POINTS = 50
REFERRED_REWARD_POINTS = 25
FIRST_PROCESSED_BOOK_POINTS = 25
POINT_EXPIRY_DAYS = 90

_CODE_CHARS = re.compile(r"[^A-Z0-9]")


def utc_now() -> datetime:
    return datetime.now(UTC)


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
