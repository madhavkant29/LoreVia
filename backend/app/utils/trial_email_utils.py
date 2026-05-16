from __future__ import annotations

from datetime import UTC, datetime, timedelta

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


def build_trial_email_schedule(started_at: datetime | None, now: datetime | None = None) -> dict[str, datetime]:
    base = started_at or now or datetime.now(UTC)
    base = base if base.tzinfo else base.replace(tzinfo=UTC)
    return {
        TRIAL_EMAIL_STARTED: base,
        TRIAL_EMAIL_NUDGE: base + timedelta(days=3),
        TRIAL_EMAIL_ENDING: base + timedelta(days=9),
        TRIAL_EMAIL_ENDED: base + timedelta(days=10),
    }
