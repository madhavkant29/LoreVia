from __future__ import annotations

import logging
import secrets
import uuid
from datetime import UTC, datetime

from fastapi import BackgroundTasks, HTTPException, Response
from redis.exceptions import RedisError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.redis import (
    mark_user_dashboard_cache_dirty,
    store_email_verification_token,
    store_refresh_session,
)
from app.core.security import create_access_token, create_refresh_token
from app.models.user import User
from app.schemas.auth import UserOut
from app.services.email_service import deliver_verification_email, send_onboarding_email
from app.services.trial_email_service import schedule_trial_email_events
from app.utils.auth_cookies import set_auth_cookies, set_device_cookie
from app.utils.auth_utils import current_token_version, password_is_valid
from app.utils.billing_utils import build_tier_presentation
from app.utils.user_utils import (
    current_daily_word_count,
    current_daily_word_goal,
    get_login_activity_dates_from_table,
    record_login_activity,
    record_login_activity_row,
)

log = logging.getLogger("lorevia.auth")


def _validate_password(password: str, email: str) -> None:
    if not password_is_valid(password, email):
        raise HTTPException(
            400,
            "Password must be at least 12 characters and include upper case, lower case, a number, a symbol, and no obvious email-based pattern.",
        )


async def _build_user_out(user: User, db: AsyncSession | None = None) -> UserOut:
    tier = build_tier_presentation(user)
    created_at = user.created_at or datetime.now(UTC)
    activity_dates = (
        await get_login_activity_dates_from_table(db, str(user.id)) if db is not None else []
    )
    return UserOut(
        id=user.id,
        email=user.email,
        username=user.username,
        tier=tier.access_tier,
        plan_tier=tier.plan_tier,
        tier_label=tier.tier_label,
        trial_active=tier.trial_active,
        trial_ends_at=tier.trial_ends_at,
        reading_mode=user.reading_mode or "casual",
        daily_word_goal=current_daily_word_goal(user),
        today_word_count=current_daily_word_count(user),
        last_login_at=user.last_login_at,
        login_streak_days=max(int(user.login_streak_days or 0), 0),
        longest_login_streak_days=max(int(user.longest_login_streak_days or 0), 0),
        login_activity_dates=activity_dates,
        email_verified=bool(user.email_verified_at),
        messaging_permission=(user.messaging_permission or "anyone"),
        created_at=created_at,
    )


async def _mint_token_pair(user: User, db: AsyncSession | None = None) -> tuple[UserOut, str, str]:
    user_id = str(user.id)
    version = current_token_version(user)
    session_id = str(uuid.uuid4())
    await store_refresh_session(
        user_id,
        session_id,
        settings.JWT_REFRESH_EXPIRE_DAYS * 24 * 60 * 60,
    )
    return (
        await _build_user_out(user, db),
        create_access_token(user_id, version),
        create_refresh_token(user_id, version, session_id),
    )


def _user_response_with_cookies(
    response: Response,
    user_out: UserOut | None,
    access_token: str,
    refresh_token: str,
    *,
    device_id: str | None = None,
) -> UserOut | None:
    set_auth_cookies(response, access_token, refresh_token)
    if device_id is not None:
        set_device_cookie(response, device_id)
    return user_out


async def _record_login_activity(
    db: AsyncSession,
    user: User,
    *,
    ip_hash: str | None = None,
    device_id: str | None = None,
) -> None:
    now = datetime.now(UTC)
    record_login_activity(user, now=now)
    await record_login_activity_row(
        db,
        str(user.id),
        now.date(),
        ip_hash=ip_hash,
        device_id=device_id,
    )
    try:
        await mark_user_dashboard_cache_dirty(str(user.id))
    except RedisError:
        log.warning(
            "login_activity_cache_invalidation_failed",
            extra={"user_id": str(user.id)},
            exc_info=True,
        )


async def _schedule_trial_email_events_best_effort(db: AsyncSession, user: User) -> None:
    try:
        async with db.begin_nested():
            await schedule_trial_email_events(db, user)
    except SQLAlchemyError:
        log.warning(
            "trial_email_schedule_failed_during_auth",
            extra={"user_id": str(user.id)},
            exc_info=True,
        )


async def _issue_email_verification(user: User) -> tuple[bool, str]:
    token = secrets.token_urlsafe(32)
    await store_email_verification_token(
        token,
        str(user.id),
        settings.EMAIL_VERIFICATION_TOKEN_TTL_SECONDS,
    )
    return await deliver_verification_email(user.email, token)


def _schedule_onboarding_email(background_tasks: BackgroundTasks, email: str) -> None:
    background_tasks.add_task(send_onboarding_email, email)
