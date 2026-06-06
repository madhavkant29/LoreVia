import logging
import secrets
import uuid
from datetime import UTC, datetime

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
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
    consume_refresh_session,
    consume_email_verification_token,
    consume_password_reset_token,
    mark_user_dashboard_cache_dirty,
    store_email_verification_token,
    store_password_reset_token,
    store_refresh_session,
)
from app.core.security import (
    DUMMY_PASSWORD_HASH,
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
    MessagingPermissionBody,
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
    device_account_limit_message,
    DeviceTrialLimitError,
    link_device_to_user_if_allowed,
)
from app.services.email_service import (
    deliver_password_reset_email,
    deliver_verification_email,
    send_onboarding_email,
)
from app.services.trial_email_service import schedule_trial_email_events
from app.utils.auth_cookies import (
    get_device_cookie,
    REFRESH_TOKEN_COOKIE_NAME,
    clear_auth_cookies,
    get_auth_token,
    resolve_device_id,
    resolve_device_id_optional,
    set_auth_cookies,
    set_device_cookie,
)
from app.utils.auth_csrf import enforce_cookie_csrf
from app.utils.auth_utils import (
    current_token_version,
    get_user_for_auth_subject,
    next_token_version,
    normalize_email,
    parse_auth_subject_uuid,
    password_is_valid,
)
from app.utils.billing_utils import build_tier_presentation
from app.utils.logging.errors import public_error_message
from app.utils.user_utils import (
    current_daily_word_count,
    current_daily_word_goal,
    get_login_activity_dates_from_table,
    record_login_activity,
    record_login_activity_row,
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


async def _build_user_out(user: User, db: AsyncSession | None = None) -> UserOut:
    tier = build_tier_presentation(user)
    created_at = user.created_at or datetime.now(UTC)
    activity_dates = await get_login_activity_dates_from_table(db, str(user.id)) if db is not None else []
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


async def _record_login_activity(
    db: AsyncSession,
    user: User,
    *,
    ip_hash: str | None = None,
    device_id: str | None = None,
) -> None:
    from datetime import UTC, datetime

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
    except Exception:
        log.warning(
            "login_activity_cache_invalidation_failed",
            extra={"user_id": str(user.id)},
            exc_info=True,
        )


async def _schedule_trial_email_events_best_effort(db: AsyncSession, user: User) -> None:
    try:
        async with db.begin_nested():
            await schedule_trial_email_events(db, user)
    except Exception:
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


def _schedule_onboarding_email(background_tasks: BackgroundTasks | None, email: str) -> None:
    if background_tasks is not None:
        background_tasks.add_task(send_onboarding_email, email)


@router.post("/register", response_model=RegisterOut, status_code=201)
async def register(
    request: Request,
    body: RegisterBody,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(rate_limit_auth_register),
):
    email = normalize_email(body.email)
    try:
        device_id = resolve_device_id(request, body.device_id)
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
        await link_device_to_user_if_allowed(db, user.id, device_id)
        await _schedule_trial_email_events_best_effort(db, user)
        await db.commit()
    except DeviceTrialLimitError as exc:
        await db.rollback()
        raise HTTPException(403, str(exc))
    except IntegrityError:
        await db.rollback()
        raise HTTPException(403, device_account_limit_message())
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
    request: Request,
    body: LoginBody,
    response: Response,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(rate_limit_auth_login),
):
    device_id = resolve_device_id_optional(request, body.device_id)
    email = normalize_email(body.email)
    user = (await db.execute(select(User).where(func.lower(User.email) == email))).scalar()
    if not user:
        verify_password(body.password, DUMMY_PASSWORD_HASH)
        raise HTTPException(401, "Invalid credentials")
    try:
        valid = verify_password(body.password, user.password_hash)
    except Exception:
        valid = False
    if not valid:
        raise HTTPException(401, "Invalid credentials")
    if not user.email_verified_at:
        raise HTTPException(403, "Please verify your email before signing in.")
    if device_id is not None:
        try:
            await link_device_to_user_if_allowed(db, user.id, device_id, strict=False)
        except DeviceTrialLimitError:
            pass
    await _record_login_activity(db, user, device_id=device_id)
    await db.commit()
    await db.refresh(user)
    user_out, access_token, refresh_token = await _mint_token_pair(user, db)
    return _user_response_with_cookies(response, user_out, access_token, refresh_token, device_id=device_id)


@router.post("/oauth/supabase", response_model=UserOut)
async def oauth_supabase(
    request: Request,
    body: SupabaseOAuthBody,
    response: Response,
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(rate_limit_auth_login),
):
    device_id = resolve_device_id_optional(request, body.device_id)
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
        raise HTTPException(503, "OAuth sign-in is not configured")
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
        raise HTTPException(503, "OAuth verification is temporarily unavailable")

    if verification_response.status_code != 200:
        log.warning(
            "Supabase OAuth verification failed: %s",
            verification_response.status_code,
        )
        raise HTTPException(401, f"Invalid sign-in token ({verification_response.status_code})")

    try:
        sb_user = verification_response.json()
    except ValueError:
        raise HTTPException(503, "OAuth verification returned invalid data")

    email = normalize_email(sb_user.get("email", ""))
    if not email:
        raise HTTPException(401, "Invalid sign-in token")
    try:
        supabase_auth_id = parse_auth_subject_uuid(sb_user.get("id"))
    except ValueError:
        raise HTTPException(401, "Invalid sign-in token")

    try:
        existing = (
            await db.execute(select(User).where(User.supabase_auth_id == supabase_auth_id))
        ).scalar_one_or_none()
        if not existing:
            existing = (await db.execute(select(User).where(func.lower(User.email) == email))).scalar()
        if existing and existing.supabase_auth_id is not None and existing.supabase_auth_id != supabase_auth_id:
            log.warning(
                "supabase_identity_mismatch",
                extra={
                    "existing_user_id": str(existing.id),
                    "existing_supabase_id": str(existing.supabase_auth_id),
                    "new_supabase_id": str(supabase_auth_id),
                    "email": email,
                },
            )
            raise HTTPException(409, "This email is already linked to another account.")
        if not existing:
            raise HTTPException(
                401,
                "No account found for this Google login. Please create an account first via the Register page.",
            )

        if device_id is not None:
            try:
                await link_device_to_user_if_allowed(db, existing.id, device_id, strict=False)
            except DeviceTrialLimitError:
                pass
        mutated = False
        if existing.supabase_auth_id is None:
            existing.supabase_auth_id = supabase_auth_id
            mutated = True
        if not existing.email_verified_at:
            existing.email_verified_at = datetime.now(UTC)
            await _schedule_trial_email_events_best_effort(db, existing)
            mutated = True
        if mutated:
            await db.commit()
            await db.refresh(existing)

        await _record_login_activity(db, existing, device_id=device_id)
        await db.commit()
        await db.refresh(existing)
        user_out, access_token, refresh_token = await _mint_token_pair(existing, db)
        return _user_response_with_cookies(response, user_out, access_token, refresh_token, device_id=device_id)
    except HTTPException:
        raise
    except Exception:
        log.exception(
            "Supabase OAuth login failed after verification",
            extra={"email": email, "has_existing_user": bool(existing) if "existing" in locals() else False},
        )
        raise HTTPException(500, public_error_message(500))


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
    user.token_version = next_token_version(user)
    await db.commit()
    return {"ok": True}


@router.post("/refresh", response_model=UserOut)
async def refresh(
    request: Request,
    response: Response,
    body: RefreshBody | None = None,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(rate_limit_auth_refresh),
):
    if body is None or not body.refresh_token:
        enforce_cookie_csrf(request)
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

    try:
        user = await get_user_for_auth_subject(db, payload["sub"])
    except ValueError:
        raise HTTPException(401, "Invalid refresh token")
    if not user:
        raise HTTPException(401, "User not found")
    current_version = current_token_version(user)
    if int(claimed_version) != current_version:
        raise HTTPException(401, "Refresh token expired")
    if not await consume_refresh_session(payload["sub"], session_id):
        raise HTTPException(401, "Refresh token expired")
    if not user.email_verified_at:
        raise HTTPException(403, "Please verify your email before signing in.")
    device_id = get_device_cookie(request)
    await _record_login_activity(db, user, device_id=device_id)
    await db.commit()
    await db.refresh(user)
    user_out, access_token, refresh_token = await _mint_token_pair(user, db)
    return _user_response_with_cookies(response, user_out, access_token, refresh_token, device_id=device_id)


@router.post("/verify-email", response_model=UserOut)
async def verify_email(
    request: Request,
    body: VerifyEmailBody,
    response: Response,
    background_tasks: BackgroundTasks = None,
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
    return _user_response_with_cookies(response, user_out, access_token, refresh_token, device_id=device_id)


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
async def logout(
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current_user.token_version = next_token_version(current_user)
    await db.commit()
    clear_auth_cookies(response)
    return {"ok": True}


@router.get("/me", response_model=UserOut)
async def me(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _record_login_activity(db, current_user, device_id=get_device_cookie(request))
    await db.commit()
    await db.refresh(current_user)
    return await _build_user_out(current_user, db)


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
    return await _build_user_out(current_user, db)


@router.patch("/me/messaging-permission", response_model=UserOut)
async def set_messaging_permission(
    body: MessagingPermissionBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current_user.messaging_permission = body.messaging_permission
    await db.commit()
    await db.refresh(current_user)
    return await _build_user_out(current_user, db)


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
        free_recall_per_day=settings.FREE_RECALL_PER_DAY,
        author_prediction_per_day=settings.AUTHOR_PREDICTION_PER_DAY,
        architect_prediction_per_day=settings.ARCHITECT_PREDICTION_PER_DAY,
        trial_high_cost_turns_per_day=settings.TRIAL_HIGH_COST_TURNS_PER_DAY,
        author_high_cost_turns_per_day=settings.AUTHOR_HIGH_COST_TURNS_PER_DAY,
        architect_high_cost_turns_per_day=settings.ARCHITECT_HIGH_COST_TURNS_PER_DAY,
        free_advisor_per_day=settings.FREE_ADVISOR_PER_DAY,
        free_advisor_per_week=settings.FREE_ADVISOR_PER_WEEK,
        free_advisor_per_month=settings.FREE_ADVISOR_PER_MONTH,
        free_continuity_per_day=settings.FREE_CONTINUITY_PER_DAY,
        author_advisor_per_day=settings.AUTHOR_ADVISOR_PER_DAY,
        author_advisor_per_week=settings.AUTHOR_ADVISOR_PER_WEEK,
        author_advisor_per_month=settings.AUTHOR_ADVISOR_PER_MONTH,
        architect_advisor_per_day=settings.ARCHITECT_ADVISOR_PER_DAY,
        architect_advisor_per_week=settings.ARCHITECT_ADVISOR_PER_WEEK,
        architect_advisor_per_month=settings.ARCHITECT_ADVISOR_PER_MONTH,
        free_continuity_per_minute=settings.FREE_CONTINUITY_PER_MINUTE,
        author_continuity_per_minute=settings.AUTHOR_CONTINUITY_PER_MINUTE,
        architect_continuity_per_minute=settings.ARCHITECT_CONTINUITY_PER_MINUTE,
    )


@router.patch("/me/username", response_model=UserOut)
async def set_username(
    username: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create or update the current user's public username."""

    username = (username or "").strip().lower()
    if not username or len(username) < 3 or len(username) > 32:
        raise HTTPException(400, "Username must be 3-32 characters")

    # Check for valid characters (alphanumeric, underscore, hyphen)
    if not all(c.isalnum() or c in "_-" for c in username):
        raise HTTPException(400, "Username can only contain letters, numbers, underscores, and hyphens")

    # Check uniqueness
    existing = (await db.execute(select(User).where(func.lower(User.username) == username.lower()))).scalar()
    if existing and existing.id != current_user.id:
        raise HTTPException(400, "Username already taken")

    current_user.username = username
    await db.commit()
    await db.refresh(current_user)
    return await _build_user_out(current_user, db)
