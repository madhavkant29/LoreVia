import logging
import secrets
import uuid
from datetime import UTC, datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.api.deps.rate_limit import (
    rate_limit_auth_login,
    rate_limit_auth_password,
    rate_limit_auth_refresh,
    rate_limit_auth_register,
)
from app.core.config import effective_tier, is_local_mode, settings
from app.core.database import get_db
from app.core.redis import (
    bump_token_version,
    consume_password_reset_token,
    get_token_version,
    refresh_session_active,
    revoke_refresh_session,
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
    ForgotPasswordBody,
    LoginBody,
    RefreshBody,
    RegisterBody,
    ResetPasswordBody,
    SupabaseOAuthBody,
    TierLimitsOut,
    UserOut,
)
from app.services.email_service import deliver_password_reset_email, send_onboarding_email
from app.utils.auth_cookies import (
    REFRESH_TOKEN_COOKIE_NAME,
    clear_auth_cookies,
    get_auth_token,
    set_auth_cookies,
)

router = APIRouter()
log = logging.getLogger("lorevia.auth")
LEGAL_VERSION = "2026-04"


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _validate_password(password: str, email: str) -> None:
    normalized_email = _normalize_email(email)
    email_local = normalized_email.split("@")[0]
    checks = [
        len(password) >= 12,
        any(ch.islower() for ch in password),
        any(ch.isupper() for ch in password),
        any(ch.isdigit() for ch in password),
        any(not ch.isalnum() for ch in password),
        email_local not in password.lower(),
        not any(password[i] == password[i + 1] == password[i + 2] for i in range(max(0, len(password) - 2))),
    ]
    if not all(checks):
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
    user_out = UserOut.model_validate(user) if user else None
    return (
        user_out,
        create_access_token(user_id, version),
        create_refresh_token(user_id, version, session_id),
    )


def _user_response_with_cookies(response: Response, user_out: UserOut | None, access_token: str, refresh_token: str) -> UserOut | None:
    set_auth_cookies(response, access_token, refresh_token)
    return user_out


@router.post("/register", response_model=UserOut, status_code=201)
async def register(
    body: RegisterBody,
    response: Response,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(rate_limit_auth_register),
):
    email = _normalize_email(body.email)
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
    db.add(user)
    await db.commit()
    await db.refresh(user)
    await send_onboarding_email(user.email)
    user_out, access_token, refresh_token = await _mint_token_pair(str(user.id), user)
    return _user_response_with_cookies(response, user_out, access_token, refresh_token)


@router.post("/login", response_model=UserOut)
async def login(
    body: LoginBody,
    response: Response,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(rate_limit_auth_login),
):
    email = _normalize_email(body.email)
    user = (await db.execute(select(User).where(func.lower(User.email) == email))).scalar()
    if not user:
        raise HTTPException(401, "Invalid credentials")
    try:
        valid = verify_password(body.password, user.password_hash)
    except Exception:
        valid = False
    if not valid:
        raise HTTPException(401, "Invalid credentials")
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
            "Supabase OAuth verification failed",
            verification_response.status_code,
        )
        raise HTTPException(401, f"Invalid Supabase token ({verification_response.status_code})")

    try:
        sb_user = verification_response.json()
    except ValueError:
        raise HTTPException(503, "Supabase OAuth verification returned invalid data")

    email = _normalize_email(sb_user.get("email", ""))
    if not email:
        raise HTTPException(401, "Invalid Supabase token")

    existing = (await db.execute(select(User).where(func.lower(User.email) == email))).scalar()
    created = False
    if not existing:
        if not body.accepted_terms:
            raise HTTPException(400, "You must accept the Terms, Compliance notice, and EULA before creating an account with Google.")
        existing = User(
            email=email,
            password_hash=hash_password(str(uuid.uuid4())),
            legal_accepted_at=datetime.now(UTC),
            legal_version=LEGAL_VERSION,
        )
        db.add(existing)
        await db.commit()
        await db.refresh(existing)
        created = True

    if created:
        await send_onboarding_email(existing.email)

    user_out, access_token, refresh_token = await _mint_token_pair(str(existing.id), existing)
    return _user_response_with_cookies(response, user_out, access_token, refresh_token)


@router.post("/forgot-password")
async def forgot_password(
    body: ForgotPasswordBody,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(rate_limit_auth_password),
):
    email = _normalize_email(body.email)
    user = (await db.execute(select(User).where(func.lower(User.email) == email))).scalar()
    if user:
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
    await revoke_refresh_session(payload["sub"], session_id)
    user_out, access_token, refresh_token = await _mint_token_pair(str(user.id), user)
    return _user_response_with_cookies(response, user_out, access_token, refresh_token)


@router.post("/logout")
async def logout(response: Response, current_user: User = Depends(get_current_user)):
    await bump_token_version(str(current_user.id))
    clear_auth_cookies(response)
    return {"ok": True}


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)):
    return UserOut(
        id=current_user.id,
        email=current_user.email,
        username=current_user.username,
        tier=effective_tier(current_user.tier),
        reading_mode=current_user.reading_mode,
        created_at=current_user.created_at,
    )


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


@router.get("/tier-limits", response_model=TierLimitsOut)
async def get_tier_limits():
    """Return configured tier limits from backend config."""
    return TierLimitsOut(
        free_max_books=settings.FREE_MAX_BOOKS,
        free_total_token_budget=settings.FREE_TOTAL_TOKEN_BUDGET,
        free_search_per_hour=settings.FREE_SEARCH_PER_HOUR,
        free_summary_per_hour=settings.FREE_SUMMARY_PER_HOUR,
        free_chat_per_day=settings.FREE_CHAT_PER_DAY,
        free_advisor_per_day=settings.FREE_ADVISOR_PER_DAY,
        free_advisor_per_week=settings.FREE_ADVISOR_PER_WEEK,
        free_advisor_per_month=settings.FREE_ADVISOR_PER_MONTH,
        pro_chat_per_day=settings.PRO_CHAT_PER_DAY,
        pro_advisor_per_day=settings.PRO_ADVISOR_PER_DAY,
        pro_advisor_per_week=settings.PRO_ADVISOR_PER_WEEK,
        pro_advisor_per_month=settings.PRO_ADVISOR_PER_MONTH,
        power_advisor_per_day=settings.POWER_ADVISOR_PER_DAY,
        power_advisor_per_week=settings.POWER_ADVISOR_PER_WEEK,
        power_advisor_per_month=settings.POWER_ADVISOR_PER_MONTH,
        free_continuity_per_minute=settings.FREE_CONTINUITY_PER_MINUTE,
        pro_continuity_per_minute=settings.PRO_CONTINUITY_PER_MINUTE,
        power_continuity_per_minute=settings.POWER_CONTINUITY_PER_MINUTE,
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

    return UserOut(
        id=current_user.id,
        email=current_user.email,
        username=current_user.username,
        tier=effective_tier(current_user.tier),
        reading_mode=current_user.reading_mode,
        created_at=current_user.created_at,
    )
