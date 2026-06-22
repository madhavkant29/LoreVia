from __future__ import annotations

import hmac
import secrets
from hashlib import sha256
from urllib.parse import urlparse

from fastapi import HTTPException, Request, Response

from app.core.config import settings
from app.utils.cookie_utils import (
    auth_cookie_secure,
    delete_cookie,
    get_request_cookie_values,
    set_cookie,
)

ADMIN_CSRF_COOKIE_NAME = "lorevia_admin_csrf"
ADMIN_CSRF_HEADER_NAME = "x-admin-csrf-token"


def _csrf_signature(nonce: str) -> str:
    return hmac.new(settings.JWT_SECRET.encode("utf-8"), nonce.encode("utf-8"), sha256).hexdigest()


def create_admin_csrf_token() -> str:
    nonce = secrets.token_urlsafe(24)
    return f"{nonce}.{_csrf_signature(nonce)}"


def set_admin_csrf_cookie(response: Response, token: str | None = None) -> str:
    resolved_token = token or create_admin_csrf_token()
    delete_cookie(response, ADMIN_CSRF_COOKIE_NAME, path="/")
    set_cookie(
        response,
        ADMIN_CSRF_COOKIE_NAME,
        resolved_token,
        max_age=60 * 60,
        httponly=False,
        secure=auth_cookie_secure(),
        samesite="lax",
        path="/",
    )
    return resolved_token


def validate_admin_csrf_token(request: Request) -> None:
    header_token = request.headers.get(ADMIN_CSRF_HEADER_NAME)
    cookie_tokens = get_request_cookie_values(request, ADMIN_CSRF_COOKIE_NAME)
    if not header_token:
        raise HTTPException(403, "Invalid admin CSRF token.")
    if not any(
        _admin_csrf_token_matches(header_token, cookie_token) for cookie_token in cookie_tokens
    ):
        raise HTTPException(403, "Invalid admin CSRF token.")

    _validate_same_origin_admin_request(request)


def _validate_same_origin_admin_request(request: Request) -> None:
    allowed_origins = {
        settings.APP_URL.rstrip("/"),
        "https://getlorevia.com",
        "https://www.getlorevia.com",
    }
    if settings.DEBUG:
        allowed_origins.update({"http://localhost:3000", "http://127.0.0.1:3000"})

    origin = request.headers.get("origin")
    referer = request.headers.get("referer")
    candidate = origin or referer
    if not candidate:
        raise HTTPException(403, "Missing admin request origin.")

    try:
        parsed = urlparse(candidate)
        request_origin = f"{parsed.scheme}://{parsed.netloc}"
    except Exception:
        raise HTTPException(403, "Invalid admin request origin.")

    if request_origin.rstrip("/") not in allowed_origins:
        raise HTTPException(403, "Invalid admin request origin.")


def _admin_csrf_token_matches(header_token: str, cookie_token: str) -> bool:
    if not hmac.compare_digest(cookie_token, header_token):
        return False
    try:
        nonce, signature = cookie_token.rsplit(".", 1)
    except ValueError:
        return False
    return bool(nonce) and hmac.compare_digest(signature, _csrf_signature(nonce))
