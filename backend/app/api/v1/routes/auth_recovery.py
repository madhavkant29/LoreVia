from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.rate_limit import rate_limit_auth_password
from app.api.v1.routes.auth_shared import (
    _issue_email_verification,
    _mint_token_pair,
    _record_login_activity,
    _schedule_onboarding_email,
    _schedule_trial_email_events_best_effort,
    _user_response_with_cookies,
    _validate_password,
)
from app.core.config import is_local_mode, settings
from app.core.database import get_db
from app.core.redis import (
    begin_password_reset_cooldown,
    consume_email_verification_token,
    consume_password_reset_token,
    store_password_reset_token,
)
from app.core.security import hash_password
from app.models.user import User
from app.schemas.auth import (
    ForgotPasswordBody,
    ResetPasswordBody,
    UserOut,
    VerifyEmailBody,
    VerifyEmailResendBody,
)
from app.services.email_service import deliver_password_reset_email
from app.utils.auth_cookies import get_device_cookie
from app.utils.auth_utils import next_token_version, normalize_email

router = APIRouter()


@router.post("/forgot-password")
async def forgot_password(
    body: ForgotPasswordBody,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(rate_limit_auth_password),
):
    email = normalize_email(body.email)
    user = (await db.execute(select(User).where(func.lower(User.email) == email))).scalar()
    if user:
        cooldown_started = await begin_password_reset_cooldown(
            str(user.id),
            settings.PASSWORD_RESET_REQUEST_COOLDOWN_SECONDS,
        )
        if not cooldown_started:
            return {"ok": True, "delivered": True}
        token = secrets.token_urlsafe(32)
        await store_password_reset_token(
            token,
            str(user.id),
            settings.PASSWORD_RESET_TOKEN_TTL_SECONDS,
        )
        delivered, reset_url = await deliver_password_reset_email(user.email, token)
        if is_local_mode():
            return {
                "ok": True,
                "delivered": delivered,
                "reset_url": reset_url,
                "message": "Email delivery failed, so the local reset link is included directly."
                if not delivered
                else "Reset email sent.",
            }
    return {"ok": True, "delivered": True}


@router.post("/reset-password")
async def reset_password(
    body: ResetPasswordBody,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(rate_limit_auth_password),
):
    user_id = await consume_password_reset_token(body.token)
    if not user_id:
        raise HTTPException(400, "Invalid or expired reset token")

    user = await db.get(User, uuid.UUID(user_id))
    if not user:
        raise HTTPException(400, "Invalid or expired reset token")

    _validate_password(body.password, user.email)
    user.password_hash = hash_password(body.password)
    user.token_version = next_token_version(user)
    await db.commit()
    return {"ok": True}


@router.post("/verify-email", response_model=UserOut)
async def verify_email(
    request: Request,
    body: VerifyEmailBody,
    response: Response,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(rate_limit_auth_password),
):
    user_id = await consume_email_verification_token(body.token)
    if not user_id:
        raise HTTPException(400, "Invalid or expired verification token")

    user = await db.get(User, uuid.UUID(user_id))
    if not user:
        raise HTTPException(400, "Invalid or expired verification token")

    newly_verified = user.email_verified_at is None
    if newly_verified:
        user.email_verified_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(user)
        await _schedule_trial_email_events_best_effort(db, user)
        await db.commit()
        _schedule_onboarding_email(background_tasks, user.email)

    device_id = get_device_cookie(request)
    await _record_login_activity(db, user, device_id=device_id)
    await db.commit()
    await db.refresh(user)
    user_out, access_token, refresh_token = await _mint_token_pair(user, db)
    return _user_response_with_cookies(
        response, user_out, access_token, refresh_token, device_id=device_id
    )


@router.post("/resend-verification")
async def resend_verification_email(
    body: VerifyEmailResendBody,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(rate_limit_auth_password),
):
    email = normalize_email(body.email)
    user = (await db.execute(select(User).where(func.lower(User.email) == email))).scalar()
    if user and not user.email_verified_at:
        delivered, verification_url = await _issue_email_verification(user)
        if is_local_mode():
            return {
                "ok": True,
                "verification_email_sent": delivered,
                "verification_url": verification_url,
            }
    return {"ok": True, "verification_email_sent": True}
