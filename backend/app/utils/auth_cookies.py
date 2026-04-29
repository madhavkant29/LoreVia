from __future__ import annotations

from fastapi import Request
from fastapi.responses import Response

from app.core.config import settings

ACCESS_TOKEN_COOKIE_NAME = "lorevia_access_token"
REFRESH_TOKEN_COOKIE_NAME = "lorevia_refresh_token"


def auth_cookie_secure() -> bool:
    return not settings.DEBUG and settings.APP_URL.startswith("https://")


def auth_cookie_path() -> str:
    return settings.API_V1_PREFIX


def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    common_kwargs = {
        "httponly": True,
        "secure": auth_cookie_secure(),
        "samesite": "lax",
        "path": auth_cookie_path(),
    }
    response.set_cookie(
        ACCESS_TOKEN_COOKIE_NAME,
        access_token,
        max_age=settings.JWT_EXPIRE_MINUTES * 60,
        **common_kwargs,
    )
    response.set_cookie(
        REFRESH_TOKEN_COOKIE_NAME,
        refresh_token,
        max_age=settings.JWT_REFRESH_EXPIRE_DAYS * 24 * 60 * 60,
        **common_kwargs,
    )


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_TOKEN_COOKIE_NAME, path=auth_cookie_path())
    response.delete_cookie(REFRESH_TOKEN_COOKIE_NAME, path=auth_cookie_path())


def get_auth_token(request: Request, bearer_token: str | None = None, cookie_name: str = ACCESS_TOKEN_COOKIE_NAME) -> str | None:
    if bearer_token:
        return bearer_token
    return request.cookies.get(cookie_name)
