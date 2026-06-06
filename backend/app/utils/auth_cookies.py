from __future__ import annotations

from fastapi import Request
from fastapi.responses import Response

from app.core.config import settings
from app.utils.auth_csrf import clear_auth_csrf_cookie, set_auth_csrf_cookie
from app.utils.auth_utils import normalize_device_id
from app.utils.cookie_utils import (
    auth_cookie_path,
    auth_cookie_secure,
    delete_cookie,
    get_request_cookie,
    legacy_cookie_paths,
    set_cookie,
)

ACCESS_TOKEN_COOKIE_NAME = "lorevia_access_token"
REFRESH_TOKEN_COOKIE_NAME = "lorevia_refresh_token"
DEVICE_ID_COOKIE_NAME = "lorevia_device_id"
DEVICE_ID_COOKIE_MAX_AGE = 365 * 24 * 60 * 60


def _clear_legacy_cookie(response: Response, cookie_name: str) -> None:
    for path in legacy_cookie_paths():
        delete_cookie(response, cookie_name, path=path)


def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    common_kwargs = {
        "httponly": True,
        "secure": auth_cookie_secure(),
        "samesite": "lax",
        "path": auth_cookie_path(),
    }
    delete_cookie(response, ACCESS_TOKEN_COOKIE_NAME, path=auth_cookie_path())
    delete_cookie(response, REFRESH_TOKEN_COOKIE_NAME, path=auth_cookie_path())
    _clear_legacy_cookie(response, ACCESS_TOKEN_COOKIE_NAME)
    _clear_legacy_cookie(response, REFRESH_TOKEN_COOKIE_NAME)
    set_cookie(
        response,
        ACCESS_TOKEN_COOKIE_NAME,
        access_token,
        max_age=settings.JWT_EXPIRE_MINUTES * 60,
        **common_kwargs,
    )
    set_cookie(
        response,
        REFRESH_TOKEN_COOKIE_NAME,
        refresh_token,
        max_age=settings.JWT_REFRESH_EXPIRE_DAYS * 24 * 60 * 60,
        **common_kwargs,
    )
    set_auth_csrf_cookie(response)


def set_device_cookie(response: Response, device_id: str) -> None:
    delete_cookie(response, DEVICE_ID_COOKIE_NAME, path=auth_cookie_path())
    _clear_legacy_cookie(response, DEVICE_ID_COOKIE_NAME)
    set_cookie(
        response,
        DEVICE_ID_COOKIE_NAME,
        normalize_device_id(device_id),
        max_age=DEVICE_ID_COOKIE_MAX_AGE,
        httponly=True,
        secure=auth_cookie_secure(),
        samesite="lax",
        path=auth_cookie_path(),
    )


def set_access_cookie(response: Response, access_token: str) -> None:
    delete_cookie(response, ACCESS_TOKEN_COOKIE_NAME, path=auth_cookie_path())
    _clear_legacy_cookie(response, ACCESS_TOKEN_COOKIE_NAME)
    set_cookie(
        response,
        ACCESS_TOKEN_COOKIE_NAME,
        access_token,
        max_age=settings.JWT_EXPIRE_MINUTES * 60,
        httponly=True,
        secure=auth_cookie_secure(),
        samesite="lax",
        path=auth_cookie_path(),
    )
    set_auth_csrf_cookie(response)


def clear_auth_cookies(response: Response) -> None:
    delete_cookie(response, ACCESS_TOKEN_COOKIE_NAME, path=auth_cookie_path())
    delete_cookie(response, REFRESH_TOKEN_COOKIE_NAME, path=auth_cookie_path())
    _clear_legacy_cookie(response, ACCESS_TOKEN_COOKIE_NAME)
    _clear_legacy_cookie(response, REFRESH_TOKEN_COOKIE_NAME)
    clear_auth_csrf_cookie(response)


def get_device_cookie(request: Request) -> str | None:
    device_id = get_request_cookie(request, DEVICE_ID_COOKIE_NAME)
    if not device_id:
        return None
    try:
        return normalize_device_id(device_id)
    except ValueError:
        return None


def resolve_device_id(request: Request, requested_device_id: str | None) -> str:
    cookie_device_id = get_device_cookie(request)
    if cookie_device_id:
        return cookie_device_id
    if requested_device_id is None:
        raise ValueError("Device identifier is required.")
    return normalize_device_id(requested_device_id)


def resolve_device_id_optional(request: Request, requested_device_id: str | None) -> str | None:
    cookie_device_id = get_device_cookie(request)
    if cookie_device_id:
        return cookie_device_id
    if requested_device_id is None:
        return None
    try:
        return normalize_device_id(requested_device_id)
    except ValueError:
        return None


def get_auth_token(request: Request, bearer_token: str | None = None, cookie_name: str = ACCESS_TOKEN_COOKIE_NAME) -> str | None:
    cookie_token = get_request_cookie(request, cookie_name)
    if cookie_token:
        return cookie_token
    if bearer_token:
        return bearer_token
    return None
