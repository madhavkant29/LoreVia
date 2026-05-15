import logging
import secrets
import uuid
from datetime import UTC, datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.api.deps.rate_limit import (
    rate_limit_auth_login,
    rate_limit_auth_password,
    rate_limit_auth_refresh,
    rate_limit_auth_register,
)
from app.core.config import is_local_mode, settings
from app.core.database import get_db
from app.core.redis import (
    begin_password_reset_cooldown,
    bump_token_version,
    consume_email_verification_token,
    consume_password_reset_token,
    get_token_version,
    refresh_session_active,
    revoke_refresh_session,
    store_email_verification_token,
    store_password_reset_token,
    store_refresh_session,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.schemas.auth import (
    DailyWordGoalBody,
    ForgotPasswordBody,
    LoginBody,
    RefreshBody,
    RegisterBody,
    RegisterOut,
    ResetPasswordBody,
    SupabaseOAuthBody,
    TierLimitsOut,
    UserOut,
    VerifyEmailBody,
    VerifyEmailResendBody,
)
from app.services.auth_service import (
    DeviceTrialLimitError,
    build_device_trial,
    ensure_device_trial_available,
)
from app.services.email_service import (
    deliver_password_reset_email,
    deliver_verification_email,
    send_onboarding_email,
)
from app.services.monetization_service import (
    create_referral_if_valid,
    ensure_referral_code,
    grant_daily_login_points,
    schedule_trial_email_events,
)
from app.utils.auth_cookies import (
    REFRESH_TOKEN_COOKIE_NAME,
    clear_auth_cookies,
    get_auth_token,
    set_auth_cookies,
)
from app.utils.auth_utils import normalize_device_id, normalize_email, password_is_valid
from app.utils.billing_utils import build_tier_presentation
from app.utils.user_utils import (
    current_daily_word_count,
    current_daily_word_goal,
    login_activity_dates,
    record_login_activity,
)

router = APIRouter()
log = logging.getLogger("lorevia.auth")
LEGAL_VERSION = "2026-04"


def _validate_password(password: str, email: str) -> None:
    if not password_is_valid(password, email):
        raise HTTPException(
            400,
            "Password must be at least 12 characters and include upper case, lower case, a number, a symbol, and no obvious email-based pattern.",
        )


async def _mint_token_pair(user_id: str, user: User | None = None) -> tuple[UserOut | None, str, str]:
    version = await get_token_version(user_id)
    session_id = str(uuid.uuid4())
    await store_refresh_session(
        user_id,
        session_id,
        settings.JWT_REFRESH_EXPIRE_DAYS * 24 * 60 * 60,
    )
    user_out = _build_user_out(user) if user else None
    return (
        user_out,
        create_access_token(user_id, version),
        create_refresh_token(user_id, version, session_id),
    )


def _user_response_with_cookies(response: Response, user_out: UserOut | None, access_token: str, refresh_token: str) -> UserOut | None:
    set_auth_cookies(response, access_token, refresh_token)
    return user_out


def _build_user_out(user: User) -> UserOut:
    tier = build_tier_presentation(user)
    created_at = user.created_at or datetime.now(UTC)
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
        login_activity_dates=login_activity_dates(user),
        email_verified=bool(user.email_verified_at),
        created_at=created_at,
    )


async def _record_login_and_apply_points(db: AsyncSession, user: User) -> None:
    record_login_activity(user)
    await grant_daily_login_points(db, user)


async def _issue_email_verification(user: User) -> tuple[bool, str]:
    token = secrets.token_urlsafe(32)
    await store_email_verification_token(
        token,
        str(user.id),
        settings.EMAIL_VERIFICATION_TOKEN_TTL_SECONDS,
    )
    return await deliver_verification_email(user.email, token)


@router.post("/register", response_model=RegisterOut, status_code=201)
async def register(
    body: RegisterBody,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(rate_limit_auth_register),
):
    email = normalize_email(body.email)
    try:
        device_id = normalize_device_id(body.device_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    username = (body.username or "").strip()
    if not body.accepted_terms:
        raise HTTPException(400, "You must accept the Terms, Compliance notice, and EULA to create an account.")
    _validate_password(body.password, email)
    if (await db.execute(select(User).where(func.lower(User.email) == email))).scalar():
        raise HTTPException(400, "Email already registered")
    if not username:
        raise HTTPException(400, "Username is required")
    if (await db.execute(select(User).where(func.lower(User.username) == username.lower()))).scalar():
        raise HTTPException(400, "Username already taken")
    try:
        await ensure_device_trial_available(db, device_id)
    except DeviceTrialLimitError as exc:
        raise HTTPException(403, str(exc))
    user = User(
        email=email,
        username=username,
        password_hash=hash_password(body.password),
        legal_accepted_at=datetime.now(UTC),
        legal_version=LEGAL_VERSION,
    )
    try:
        db.add(user)
        await db.flush()
        await ensure_referral_code(db, user)
        await create_referral_if_valid(db, user, body.referral_code)
        await schedule_trial_email_events(db, user)
        db.add(build_device_trial(user.id, device_id))
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(403, f"This device has already used the maximum of {settings.DEVICE_TRIAL_MAX_ACCOUNTS} trial accounts.")
    await db.refresh(user)
    delivered, verification_url = await _issue_email_verification(user)
    return RegisterOut(
        id=user.id,
        email=user.email,
        username=user.username or username,
        verification_email_sent=delivered,
        verification_url=verification_url if is_local_mode() else None,
    )


@router.post("/login", response_model=UserOut)
async def login(
    body: LoginBody,
    response: Response,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(rate_limit_auth_login),
):
    email = normalize_email(body.email)
    user = (await db.execute(select(User).where(func.lower(User.email) == email))).scalar()
    if not user:
        raise HTTPException(401, "Invalid credentials")
    try:
        valid = verify_password(body.password, user.password_hash)
    except Exception:
        valid = False
    if not valid:
        raise HTTPException(401, "Invalid credentials")
    if not user.email_verified_at:
        raise HTTPException(403, "Please verify your email before signing in.")
    await _record_login_and_apply_points(db, user)
    await db.commit()
    await db.refresh(user)
    user_out, access_token, refresh_token = await _mint_token_pair(str(user.id), user)
    return _user_response_with_cookies(response, user_out, access_token, refresh_token)


@router.post("/oauth/supabase", response_model=UserOut)
async def oauth_supabase(
    body: SupabaseOAuthBody,
    response: Response,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(rate_limit_auth_login),
):
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
        raise HTTPException(503, "Supabase OAuth is not configured")
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            verification_response = await client.get(
                f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/user",
                headers={
                    "apikey": settings.SUPABASE_SERVICE_KEY,
                    "Authorization": f"Bearer {body.token}",
                },
            )
    except httpx.HTTPError:
        log.exception("Supabase OAuth verification request failed")
        raise HTTPException(503, "Supabase OAuth verification is unavailable")

    if verification_response.status_code != 200:
        log.warning(
            "Supabase OAuth verification failed: %s",
            verification_response.status_code,
        )
        raise HTTPException(401, f"Invalid Supabase token ({verification_response.status_code})")

    try:
        sb_user = verification_response.json()
    except ValueError:
        raise HTTPException(503, "Supabase OAuth verification returned invalid data")

    email = normalize_email(sb_user.get("email", ""))
    if not email:
        raise HTTPException(401, "Invalid Supabase token")

    try:
        existing = (await db.execute(select(User).where(func.lower(User.email) == email))).scalar()
        created = False
        if not existing:
            try:
                device_id = normalize_device_id(body.device_id)
            except ValueError as exc:
                raise HTTPException(400, str(exc))
            local_supabase_recovery = settings.DEBUG
            if not body.accepted_terms and not local_supabase_recovery:
                raise HTTPException(400, "You must accept the Terms, Compliance notice, and EULA before creating an account with Google.")
            if not local_supabase_recovery:
                try:
                    await ensure_device_trial_available(db, device_id)
                except DeviceTrialLimitError as exc:
                    raise HTTPException(403, str(exc))
            existing = User(
                email=email,
                password_hash=hash_password(str(uuid.uuid4())),
                legal_accepted_at=datetime.now(UTC) if (body.accepted_terms or local_supabase_recovery) else None,
                legal_version=LEGAL_VERSION,
                email_verified_at=datetime.now(UTC),
            )
            try:
                db.add(existing)
                await db.flush()
                await ensure_referral_code(db, existing)
                await create_referral_if_valid(db, existing, body.referral_code)
                await schedule_trial_email_events(db, existing)
                if not local_supabase_recovery:
                    db.add(build_device_trial(existing.id, device_id))
                await db.commit()
            except IntegrityError:
                await db.rollback()
                raise HTTPException(403, f"This device has already used the maximum of {settings.DEVICE_TRIAL_MAX_ACCOUNTS} trial accounts.")
            await db.refresh(existing)
            created = True
        elif not existing.email_verified_at:
            existing.email_verified_at = datetime.now(UTC)
            await ensure_referral_code(db, existing)
            await schedule_trial_email_events(db, existing)
            await db.commit()
            await db.refresh(existing)

        if created:
            await send_onboarding_email(existing.email)

        await _record_login_and_apply_points(db, existing)
        await db.commit()
        await db.refresh(existing)
        user_out, access_token, refresh_token = await _mint_token_pair(str(existing.id), existing)
        return _user_response_with_cookies(response, user_out, access_token, refresh_token)
    except HTTPException:
        raise
    except Exception:
        log.exception(
            "Supabase OAuth login failed after verification",
            extra={"email": email, "has_existing_user": bool(existing) if "existing" in locals() else False},
        )
        raise


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
                "message": "Email delivery failed, so the local reset link is included directly." if not delivered else "Reset email sent.",
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
    await db.commit()
    await bump_token_version(str(user.id))
    return {"ok": True}


@router.post("/refresh", response_model=UserOut)
async def refresh(
    request: Request,
    response: Response,
    body: RefreshBody | None = None,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(rate_limit_auth_refresh),
):
    refresh_token = body.refresh_token if body and body.refresh_token else get_auth_token(request, cookie_name=REFRESH_TOKEN_COOKIE_NAME)
    if not refresh_token:
        raise HTTPException(401, "Invalid refresh token")
    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(401, "Invalid refresh token")
    claimed_version = payload.get("ver")
    session_id = payload.get("sid")
    if claimed_version is None or not session_id:
        raise HTTPException(401, "Invalid refresh token")

    current_version = await get_token_version(payload["sub"])
    if int(claimed_version) != current_version:
        raise HTTPException(401, "Refresh token expired")
    if not await refresh_session_active(payload["sub"], session_id):
        raise HTTPException(401, "Refresh token expired")

    user = await db.get(User, uuid.UUID(payload["sub"]))
    if not user:
        raise HTTPException(401, "User not found")
    if not user.email_verified_at:
        raise HTTPException(403, "Please verify your email before signing in.")
    await revoke_refresh_session(payload["sub"], session_id)
    await _record_login_and_apply_points(db, user)
    await db.commit()
    await db.refresh(user)
    user_out, access_token, refresh_token = await _mint_token_pair(str(user.id), user)
    return _user_response_with_cookies(response, user_out, access_token, refresh_token)


@router.post("/verify-email", response_model=UserOut)
async def verify_email(
    body: VerifyEmailBody,
    response: Response,
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
        await schedule_trial_email_events(db, user)
        await db.commit()
        await send_onboarding_email(user.email)

    await _record_login_and_apply_points(db, user)
    await db.commit()
    await db.refresh(user)
    user_out, access_token, refresh_token = await _mint_token_pair(str(user.id), user)
    return _user_response_with_cookies(response, user_out, access_token, refresh_token)


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


@router.post("/logout")
async def logout(response: Response, current_user: User = Depends(get_current_user)):
    await bump_token_version(str(current_user.id))
    clear_auth_cookies(response)
    return {"ok": True}


@router.get("/me", response_model=UserOut)
async def me(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _record_login_and_apply_points(db, current_user)
    await db.commit()
    await db.refresh(current_user)
    return _build_user_out(current_user)


@router.patch("/me/reading-mode")
async def set_reading_mode(
    mode: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if mode not in ("casual", "analyst", "speed"):
        raise HTTPException(400, "Invalid mode")
    current_user.reading_mode = mode
    await db.commit()
    return {"reading_mode": mode}


@router.patch("/me/daily-word-goal", response_model=UserOut)
async def set_daily_word_goal(
    body: DailyWordGoalBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current_user.daily_word_goal = body.daily_word_goal
    await db.commit()
    await db.refresh(current_user)
    return _build_user_out(current_user)


@router.get("/tier-limits", response_model=TierLimitsOut)
async def get_tier_limits():
    """Return configured tier limits from backend config."""
    return TierLimitsOut(
        free_max_books=settings.FREE_MAX_BOOKS,
        author_max_uploads=settings.AUTHOR_MAX_UPLOADS,
        architect_uploads_unlimited=True,
        free_total_token_budget=settings.FREE_TOTAL_TOKEN_BUDGET,
        free_search_per_day=settings.FREE_SEARCH_PER_DAY,
        free_summary_per_hour=settings.FREE_SUMMARY_PER_HOUR,
        free_prediction_per_day=settings.FREE_PREDICTION_PER_DAY,
        reader_prediction_per_day=settings.READER_PREDICTION_PER_DAY,
        author_prediction_per_day=settings.AUTHOR_PREDICTION_PER_DAY,
        architect_prediction_per_day=settings.ARCHITECT_PREDICTION_PER_DAY,
        trial_high_cost_turns_per_day=settings.TRIAL_HIGH_COST_TURNS_PER_DAY,
        author_high_cost_turns_per_day=settings.AUTHOR_HIGH_COST_TURNS_PER_DAY,
        architect_high_cost_turns_per_day=settings.ARCHITECT_HIGH_COST_TURNS_PER_DAY,
        free_advisor_per_day=settings.FREE_ADVISOR_PER_DAY,
        free_advisor_per_week=settings.FREE_ADVISOR_PER_WEEK,
        free_advisor_per_month=settings.FREE_ADVISOR_PER_MONTH,
        reader_advisor_per_day=settings.READER_ADVISOR_PER_DAY,
        reader_advisor_per_week=settings.READER_ADVISOR_PER_WEEK,
        reader_advisor_per_month=settings.READER_ADVISOR_PER_MONTH,
        author_advisor_per_day=settings.AUTHOR_ADVISOR_PER_DAY,
        author_advisor_per_week=settings.AUTHOR_ADVISOR_PER_WEEK,
        author_advisor_per_month=settings.AUTHOR_ADVISOR_PER_MONTH,
        architect_advisor_per_day=settings.ARCHITECT_ADVISOR_PER_DAY,
        architect_advisor_per_week=settings.ARCHITECT_ADVISOR_PER_WEEK,
        architect_advisor_per_month=settings.ARCHITECT_ADVISOR_PER_MONTH,
        free_continuity_per_minute=settings.FREE_CONTINUITY_PER_MINUTE,
        reader_continuity_per_minute=settings.READER_CONTINUITY_PER_MINUTE,
        author_continuity_per_minute=settings.AUTHOR_CONTINUITY_PER_MINUTE,
        architect_continuity_per_minute=settings.ARCHITECT_CONTINUITY_PER_MINUTE,
    )


@router.patch("/me/username", response_model=UserOut)
async def set_username(
    username: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Set username for existing users. Username cannot be changed once set."""
    if current_user.username:
        raise HTTPException(400, "Username already set")

    username = (username or "").strip().lower()
    if not username or len(username) < 3 or len(username) > 32:
        raise HTTPException(400, "Username must be 3-32 characters")

    # Check for valid characters (alphanumeric, underscore, hyphen)
    if not all(c.isalnum() or c in "_-" for c in username):
        raise HTTPException(400, "Username can only contain letters, numbers, underscores, and hyphens")

    # Check uniqueness
    existing = (await db.execute(select(User).where(func.lower(User.username) == username.lower()))).scalar()
    if existing:
        raise HTTPException(400, "Username already taken")

    current_user.username = username
    await db.commit()
    await db.refresh(current_user)
    return _build_user_out(current_user)
