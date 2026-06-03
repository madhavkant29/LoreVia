import logging
import uuid
from typing import Any

from fastapi import Depends, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import get_redis, key_admin_step_up, refresh_session_active
from app.core.security import create_access_token, decode_token
from app.models.user import User
from app.services.admin_service import (
    ADMIN_SCOPE_BILLING,
    ADMIN_SCOPE_MODERATION,
    ADMIN_SCOPE_SUPER,
    get_active_admin_principal,
    principal_has_scope,
    principal_scope_snapshot,
    record_admin_audit_event,
)
from app.utils.auth_utils import current_token_version, get_user_for_auth_subject
from app.utils.auth_cookies import (
    REFRESH_TOKEN_COOKIE_NAME,
    get_auth_token,
    set_access_cookie,
)
from app.utils.auth_csrf import _has_valid_bearer_access_token, enforce_cookie_csrf
from app.utils.admin_security import validate_admin_csrf_token
from app.utils.request_context import set_request_user_id

bearer = HTTPBearer(auto_error=False)
log = logging.getLogger("lorevia.auth")


def _claim_version(payload: dict[str, Any]) -> int:
    try:
        raw_version = payload.get("ver")
        if raw_version is None:
            raise ValueError("missing version")
        return int(raw_version)
    except (TypeError, ValueError):
        raise HTTPException(401, "Invalid or expired token")


def _decode_access_payload(token: str | None) -> dict[str, Any] | None:
    if not token:
        return None
    try:
        payload = decode_token(token)
    except Exception:
        return None
    if not payload:
        return None
    if payload.get("type") != "access":
        return None
    return payload


def _decode_refresh_payload(token: str | None) -> dict[str, Any] | None:
    if not token:
        return None
    try:
        payload = decode_token(token)
    except Exception:
        return None
    if not payload:
        return None
    if payload.get("type") != "refresh":
        return None
    return payload


async def _load_user_from_claims(user_id: str, claimed_version: int, db: AsyncSession) -> User:
    try:
        user = await get_user_for_auth_subject(db, user_id)
    except ValueError:
        raise HTTPException(401, "Invalid or expired token")
    except Exception:
        log.exception("database_unavailable_during_auth", extra={"user_id": user_id})
        raise HTTPException(503, "Authentication service temporarily unavailable")

    if not user:
        raise HTTPException(401, "User not found")

    current_version = current_token_version(user)
    if claimed_version != current_version:
        # Do NOT bump the version here — bumping on every mismatch causes the
        # stored version to drift away from valid tokens and can permanently
        # lock users out on retry.
        raise HTTPException(401, "Session expired. Please sign in again.")

    set_request_user_id(user.id)
    return user


async def get_current_user(
    request: Request,
    response: Response,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    enforce_cookie_csrf(request)
    access_token = get_auth_token(request, credentials.credentials if credentials else None)
    access_payload = _decode_access_payload(access_token)
    if access_payload:
        try:
            return await _load_user_from_claims(access_payload["sub"], _claim_version(access_payload), db)
        except HTTPException as exc:
            # Some browsers can retain a stale access cookie alongside a newer
            # refresh cookie when users switch accounts or a cookie path changes.
            # If the access token resolves to a missing user, fall back to the
            # refresh token before failing the request.
            if exc.status_code != 401:
                raise
            log.debug("access_token_fallback_to_refresh", extra={"user_id": access_payload.get("sub")})

    refresh_token = get_auth_token(request, cookie_name=REFRESH_TOKEN_COOKIE_NAME)
    refresh_payload = _decode_refresh_payload(refresh_token)
    if not refresh_payload:
        raise HTTPException(401, "Invalid or expired token")

    claimed_version = _claim_version(refresh_payload)
    session_id = refresh_payload.get("sid")
    if not session_id:
        raise HTTPException(401, "Invalid or expired token")

    user_id = refresh_payload["sub"]
    user = await _load_user_from_claims(user_id, claimed_version, db)

    try:
        session_active = await refresh_session_active(user_id, session_id)
    except Exception:
        log.exception("redis_unavailable_during_auth", extra={"user_id": user_id, "session_id": session_id})
        raise HTTPException(503, "Authentication service temporarily unavailable")

    if not session_active:
        raise HTTPException(401, "Session expired. Please sign in again.")

    set_access_cookie(response, create_access_token(str(user.id), claimed_version))
    return user


async def get_optional_current_user(
    request: Request,
    response: Response,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    try:
        return await get_current_user(request=request, response=response, credentials=credentials, db=db)
    except HTTPException as exc:
        if exc.status_code in {401, 503}:
            return None
        raise


async def get_admin(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    return await require_admin_principal(request=request, current_user=current_user, db=db)


async def require_admin_principal(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    principal = await get_active_admin_principal(db, current_user.id)
    if principal is None:
        await record_admin_audit_event(
            db,
            actor_user_id=current_user.id,
            action_type="admin_access_denied",
            result="denied",
            reason="No active admin principal.",
            request=request,
        )
        await db.commit()
        raise HTTPException(403, "Admin only")
    request.state.admin_principal = principal
    return current_user


async def _require_admin_scope(
    *,
    request: Request,
    current_user: User,
    db: AsyncSession,
    required_scope: str,
) -> User:
    principal = await get_active_admin_principal(db, current_user.id)
    if not principal_has_scope(principal, required_scope):
        await record_admin_audit_event(
            db,
            actor_user_id=current_user.id,
            action_type=f"admin_scope_denied:{required_scope}",
            result="denied",
            reason="Missing required admin scope.",
            request=request,
            scopes_snapshot=principal_scope_snapshot(principal),
        )
        await db.commit()
        raise HTTPException(403, "Admin only")
    request.state.admin_principal = principal
    return current_user


async def require_moderation_admin(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    return await _require_admin_scope(
        request=request,
        current_user=current_user,
        db=db,
        required_scope=ADMIN_SCOPE_MODERATION,
    )


async def require_billing_admin(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    return await _require_admin_scope(
        request=request,
        current_user=current_user,
        db=db,
        required_scope=ADMIN_SCOPE_BILLING,
    )


async def require_super_admin(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    return await _require_admin_scope(
        request=request,
        current_user=current_user,
        db=db,
        required_scope=ADMIN_SCOPE_SUPER,
    )


async def require_owner_admin(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    principal = await get_active_admin_principal(db, current_user.id)
    if principal is None or not principal.is_owner:
        await record_admin_audit_event(
            db,
            actor_user_id=current_user.id,
            action_type="admin_owner_denied",
            result="denied",
            reason="Owner admin access is required.",
            request=request,
            scopes_snapshot=principal_scope_snapshot(principal),
        )
        await db.commit()
        raise HTTPException(403, "Admin only")
    request.state.admin_principal = principal
    return current_user


async def require_admin_csrf(request: Request) -> None:
    authorization = request.headers.get("authorization", "")
    if _has_valid_bearer_access_token(authorization):
        return
    validate_admin_csrf_token(request)


def _current_admin_session_id(request: Request) -> str:
    refresh_payload = _decode_refresh_payload(get_auth_token(request, cookie_name=REFRESH_TOKEN_COOKIE_NAME))
    if refresh_payload and refresh_payload.get("sid"):
        return str(refresh_payload["sid"])
    log.warning("admin_session_fallback_no_refresh_cookie")
    return "access"


async def mark_admin_step_up(request: Request, user_id: uuid.UUID, ttl_seconds: int = 10 * 60) -> None:
    session_id = _current_admin_session_id(request)
    r = await get_redis()
    await r.setex(key_admin_step_up(str(user_id), session_id), ttl_seconds, "1")


async def admin_step_up_active(request: Request, user_id: uuid.UUID) -> bool:
    session_id = _current_admin_session_id(request)
    r = await get_redis()
    return bool(await r.exists(key_admin_step_up(str(user_id), session_id)))


async def require_admin_step_up(
    request: Request,
    current_user: User = Depends(require_admin_principal),
) -> None:
    if await admin_step_up_active(request, current_user.id):
        return
    raise HTTPException(403, "Recent admin verification required.")
