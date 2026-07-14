import logging
import secrets
import uuid
from datetime import UTC, datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.rate_limit import (
    rate_limit_auth_login,
    rate_limit_auth_refresh,
    rate_limit_auth_register,
)
from app.api.v1.routes import auth_account, auth_recovery
from app.api.v1.routes.auth_shared import (
    _build_user_out,
    _issue_email_verification,
    _mint_token_pair,
    _record_login_activity,
    _schedule_trial_email_events_best_effort,
    _user_response_with_cookies,
    _validate_password,
)
from app.core.config import is_local_mode, settings
from app.core.database import get_db
from app.core.redis import consume_refresh_session
from app.core.security import (
    DUMMY_PASSWORD_HASH,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.schemas.auth import (
    LoginBody,
    RefreshBody,
    RegisterBody,
    RegisterOut,
    SupabaseOAuthBody,
    UserOut,
)
from app.services.auth_service import (
    DeviceTrialLimitError,
    device_account_limit_message,
    link_device_to_user_if_allowed,
)
from app.utils.auth_cookies import (
    REFRESH_TOKEN_COOKIE_NAME,
    get_auth_token,
    get_device_cookie,
    resolve_device_id,
    resolve_device_id_optional,
)
from app.utils.auth_csrf import enforce_cookie_csrf
from app.utils.auth_utils import (
    current_token_version,
    get_user_for_auth_subject,
    normalize_email,
    parse_auth_subject_uuid,
    verify_password_safely,
)
from app.utils.logging.errors import public_error_message
from app.utils.privacy_utils import user_is_deleted

router = APIRouter()
router.include_router(auth_recovery.router)
router.include_router(auth_account.router)
log = logging.getLogger("lorevia.auth")
LEGAL_VERSION = "2026-04"
SUPABASE_OAUTH_PERSISTENCE_EXCEPTIONS = (RuntimeError, ValueError, SQLAlchemyError)

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
        raise HTTPException(
            400, "You must accept the Terms, Compliance notice, and EULA to create an account."
        )
    _validate_password(body.password, email)
    if (await db.execute(select(User).where(func.lower(User.email) == email))).scalar():
        raise HTTPException(400, "Email already registered")
    if not username:
        raise HTTPException(400, "Username is required")
    if (
        await db.execute(select(User).where(func.lower(User.username) == username.lower()))
    ).scalar():
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
    if user_is_deleted(user):
        raise HTTPException(401, "Account has been deleted.")
    if not verify_password_safely(body.password, user.password_hash):
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
    return _user_response_with_cookies(
        response, user_out, access_token, refresh_token, device_id=device_id
    )


@router.post("/oauth/supabase", response_model=UserOut)
async def oauth_supabase(
    request: Request,
    body: SupabaseOAuthBody,
    response: Response,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(rate_limit_auth_login),
):
    device_id = resolve_device_id_optional(request, body.device_id)
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
        log.error(
            "supabase_oauth_config_missing",
            extra={
                "has_url": bool(settings.SUPABASE_URL),
                "has_key": bool(settings.SUPABASE_SERVICE_KEY),
            },
        )
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
    except httpx.TimeoutException:
        log.exception("Supabase OAuth verification timed out")
        raise HTTPException(503, "OAuth verification timed out. Please try again.")
    except httpx.HTTPError:
        log.exception("Supabase OAuth verification request failed")
        raise HTTPException(503, "OAuth verification is temporarily unavailable")

    if verification_response.status_code != 200:
        log.warning(
            "Supabase OAuth verification failed",
            extra={
                "status_code": verification_response.status_code,
                "response_text": verification_response.text[:500]
                if verification_response.text
                else None,
            },
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
            existing = (
                await db.execute(select(User).where(func.lower(User.email) == email))
            ).scalar()
        if (
            existing
            and existing.supabase_auth_id is not None
            and existing.supabase_auth_id != supabase_auth_id
        ):
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
            # If accepted_terms is True, this is a registration flow from the /register page
            # Create a new account for this Google user
            if body.accepted_terms:
                log.info(
                    "supabase_oauth_creating_new_user",
                    extra={
                        "supabase_auth_id": str(supabase_auth_id),
                        "email": email,
                    },
                )
                try:
                    existing = User(
                        email=email,
                        supabase_auth_id=supabase_auth_id,
                        email_verified_at=datetime.now(UTC),
                        password_hash=hash_password(secrets.token_urlsafe(32)),
                    )
                    db.add(existing)
                    await db.flush()

                    if device_id is not None:
                        try:
                            await link_device_to_user_if_allowed(
                                db, existing.id, device_id, strict=True
                            )
                        except DeviceTrialLimitError as e:
                            await db.rollback()
                            raise HTTPException(429, str(e))

                    await db.commit()
                    await db.refresh(existing)
                    await _schedule_trial_email_events_best_effort(db, existing)
                    await _record_login_activity(db, existing, device_id=device_id)
                    await db.commit()
                    await db.refresh(existing)

                    user_out, access_token, refresh_token = await _mint_token_pair(existing, db)
                    return _user_response_with_cookies(
                        response, user_out, access_token, refresh_token, device_id=device_id
                    )
                except SUPABASE_OAUTH_PERSISTENCE_EXCEPTIONS:
                    await db.rollback()
                    raise
            else:
                # This is a login attempt from /login page, but no account exists
                log.info(
                    "supabase_oauth_no_user_found",
                    extra={
                        "supabase_auth_id": str(supabase_auth_id),
                        "email": email,
                    },
                )
                raise HTTPException(
                    401,
                    "No account found for this Google login. Please create an account first via the Register page.",
                )

        if user_is_deleted(existing):
            raise HTTPException(401, "Account has been deleted.")

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
        return _user_response_with_cookies(
            response, user_out, access_token, refresh_token, device_id=device_id
        )
    except HTTPException:
        raise
    except SUPABASE_OAUTH_PERSISTENCE_EXCEPTIONS:
        log.exception(
            "Supabase OAuth login failed after verification",
            extra={
                "email": email,
                "has_existing_user": bool(existing) if "existing" in locals() else False,
            },
        )
        raise HTTPException(500, public_error_message(500))


@router.post("/session", response_model=UserOut)
async def session(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    access_token = get_auth_token(request)
    access_payload = decode_token(access_token) if access_token else None
    if access_payload and access_payload.get("type") == "access":
        try:
            claimed_version = int(access_payload.get("ver"))
        except (TypeError, ValueError):
            claimed_version = -1
        try:
            user = await get_user_for_auth_subject(db, access_payload.get("sub"))
        except ValueError:
            user = None
        if (
            user
            and not user_is_deleted(user)
            and claimed_version == current_token_version(user)
            and user.email_verified_at
        ):
            return await _build_user_out(user, db)

    enforce_cookie_csrf(request)
    await rate_limit_auth_refresh(request)

    refresh_token = get_auth_token(request, cookie_name=REFRESH_TOKEN_COOKIE_NAME)
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
    if user_is_deleted(user):
        raise HTTPException(401, "Account has been deleted.")
    current_version = current_token_version(user)
    if int(claimed_version) != current_version:
        raise HTTPException(401, "Refresh token expired")
    if not await consume_refresh_session(payload["sub"], session_id):
        raise HTTPException(401, "Refresh token expired")
    if not user.email_verified_at:
        raise HTTPException(403, "Please verify your email before signing in.")
    device_id = get_device_cookie(request)
    user_out, access_token, refresh_token = await _mint_token_pair(user, db)
    return _user_response_with_cookies(
        response, user_out, access_token, refresh_token, device_id=device_id
    )


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
    refresh_token = (
        body.refresh_token
        if body and body.refresh_token
        else get_auth_token(request, cookie_name=REFRESH_TOKEN_COOKIE_NAME)
    )
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
    if user_is_deleted(user):
        raise HTTPException(401, "Account has been deleted.")
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
    return _user_response_with_cookies(
        response, user_out, access_token, refresh_token, device_id=device_id
    )
