from __future__ import annotations

import hmac
import secrets
from hashlib import sha256
from urllib.parse import urlparse

from fastapi import HTTPException, Request
from fastapi.responses import Response

from app.core.config import cors_origins, settings
from app.core.security import decode_token
from app.utils.cookie_utils import (
    auth_cookie_path,
    auth_cookie_secure,
    delete_cookie,
    get_request_cookie,
    get_request_cookie_values,
    legacy_cookie_paths,
    set_cookie,
)

AUTH_CSRF_COOKIE_NAME = "lorevia_csrf"
AUTH_CSRF_HEADER_NAME = "x-csrf-token"
UNSAFE_HTTP_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def create_auth_csrf_token() -> str:
    nonce = secrets.token_urlsafe(24)
    signature = hmac.new(
        settings.JWT_SECRET.encode("utf-8"), nonce.encode("utf-8"), sha256
    ).hexdigest()
    return f"{nonce}.{signature}"


def set_auth_csrf_cookie(response: Response, token: str | None = None) -> str:
    resolved_token = token or create_auth_csrf_token()
    delete_cookie(response, AUTH_CSRF_COOKIE_NAME, path=auth_cookie_path())
    _clear_legacy_auth_csrf_cookie(response)
    set_cookie(
        response,
        AUTH_CSRF_COOKIE_NAME,
        resolved_token,
        max_age=settings.JWT_REFRESH_EXPIRE_DAYS * 24 * 60 * 60,
        httponly=False,
        secure=auth_cookie_secure(),
        samesite="lax",
        path=auth_cookie_path(),
    )
    return resolved_token


def clear_auth_csrf_cookie(response: Response) -> None:
    delete_cookie(response, AUTH_CSRF_COOKIE_NAME, path=auth_cookie_path())
    _clear_legacy_auth_csrf_cookie(response)


def validate_auth_csrf_token(request: Request) -> None:
    header_token = request.headers.get(AUTH_CSRF_HEADER_NAME)
    cookie_tokens = get_request_cookie_values(request, AUTH_CSRF_COOKIE_NAME)
    if not header_token:
        raise HTTPException(403, "Invalid CSRF token.")
    if not any(_csrf_token_matches(header_token, cookie_token) for cookie_token in cookie_tokens):
        raise HTTPException(403, "Invalid CSRF token.")

    _validate_same_origin_request(request)


def cookie_authenticated_request_requires_csrf(request: Request) -> bool:
    if request.method.upper() not in UNSAFE_HTTP_METHODS:
        return False
    authorization = request.headers.get("authorization", "")
    return not _has_valid_bearer_access_token(authorization)


def enforce_cookie_csrf(request: Request) -> None:
    if cookie_authenticated_request_requires_csrf(request):
        validate_auth_csrf_token(request)


def _has_valid_bearer_access_token(authorization: str) -> bool:
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return False
    payload = decode_token(token.strip())
    return bool(payload and payload.get("type") == "access" and payload.get("sub"))


def _validate_same_origin_request(request: Request) -> None:
    allowed_origins = {
        settings.APP_URL.rstrip("/"),
        "https://getlorevia.com",
        "https://www.getlorevia.com",
    }
    allowed_origins.update(origin.rstrip("/") for origin in cors_origins() if origin != "*")
    if settings.DEBUG:
        allowed_origins.update({"http://localhost:3000", "http://127.0.0.1:3000"})

    origin = request.headers.get("origin")
    referer = request.headers.get("referer")
    candidate = origin or referer
    if not candidate:
        raise HTTPException(403, "Missing request origin.")

    try:
        parsed = urlparse(candidate)
        request_origin = f"{parsed.scheme}://{parsed.netloc}"
    except ValueError:
        raise HTTPException(403, "Invalid request origin.")

    if settings.DEBUG and parsed.scheme in {"http", "https"} and parsed.hostname in {"localhost", "127.0.0.1", "[::1]", "::1"}:
        return
    if request_origin.rstrip("/") not in allowed_origins:
        raise HTTPException(403, "Invalid request origin.")


def _clear_legacy_auth_csrf_cookie(response: Response) -> None:
    for path in legacy_cookie_paths():
        delete_cookie(response, AUTH_CSRF_COOKIE_NAME, path=path)


def _csrf_token_matches(header_token: str, cookie_token: str) -> bool:
    if not hmac.compare_digest(cookie_token, header_token):
        return False
    try:
        nonce, signature = cookie_token.rsplit(".", 1)
    except ValueError:
        return False
    expected_signature = hmac.new(
        settings.JWT_SECRET.encode("utf-8"), nonce.encode("utf-8"), sha256
    ).hexdigest()
    return bool(nonce) and hmac.compare_digest(signature, expected_signature)
