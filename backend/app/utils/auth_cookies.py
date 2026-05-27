from __future__ import annotations

from fastapi import Request
from fastapi.responses import Response

from app.core.config import settings
from app.utils.auth_csrf import clear_auth_csrf_cookie, set_auth_csrf_cookie
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


def get_auth_token(request: Request, bearer_token: str | None = None, cookie_name: str = ACCESS_TOKEN_COOKIE_NAME) -> str | None:
    cookie_token = get_request_cookie(request, cookie_name)
    if cookie_token:
        return cookie_token
    if bearer_token:
        return bearer_token
    return None
