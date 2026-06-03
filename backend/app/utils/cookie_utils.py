from __future__ import annotations

import ipaddress
from urllib.parse import unquote, urlparse

from fastapi import Request
from fastapi.responses import Response

from app.core.config import settings


def auth_cookie_secure() -> bool:
    return not settings.DEBUG and settings.APP_URL.startswith("https://")


def auth_cookie_path() -> str:
    # Admin pages are server-rendered outside the API prefix and need the same
    # auth cookies on the initial page request.
    return "/"


def auth_cookie_domain() -> str | None:
    configured_domain = str(settings.AUTH_COOKIE_DOMAIN or "").strip().lower().lstrip(".").rstrip(".")
    if not configured_domain:
        return None
    try:
        hostname = (urlparse(settings.APP_URL).hostname or "").strip().lower().rstrip(".")
    except Exception:
        return None
    if not hostname or configured_domain in {"localhost", "127.0.0.1", "::1"}:
        return None
    try:
        ipaddress.ip_address(configured_domain)
        return None
    except ValueError:
        pass
    if hostname != configured_domain and not hostname.endswith(f".{configured_domain}"):
        return None
    return configured_domain


def set_cookie(response: Response, key: str, value: str, **kwargs) -> None:
    domain = auth_cookie_domain()
    if domain:
        kwargs.setdefault("domain", domain)
    response.set_cookie(key, value, **kwargs)


def delete_cookie(response: Response, key: str, *, path: str) -> None:
    response.delete_cookie(key, path=path)
    domain = auth_cookie_domain()
    if domain:
        response.delete_cookie(key, path=path, domain=domain)


def legacy_cookie_paths() -> tuple[str, ...]:
    legacy_path = (settings.API_V1_PREFIX or "").rstrip("/") or "/"
    current_path = auth_cookie_path()
    candidates = {
        legacy_path,
        f"{legacy_path}/" if legacy_path != "/" else "/",
        f"{legacy_path}/auth",
        f"{legacy_path}/auth/",
    }
    return tuple(path for path in candidates if path and path != current_path)


def get_request_cookie(request: Request, cookie_name: str) -> str | None:
    values = get_request_cookie_values(request, cookie_name)
    return values[-1] if values else None


def get_request_cookie_values(request: Request, cookie_name: str) -> list[str]:
    raw_cookie_header = request.headers.get("cookie")
    values: list[str] = []
    if raw_cookie_header:
        for part in raw_cookie_header.split(";"):
            name, separator, value = part.strip().partition("=")
            if separator and name == cookie_name:
                values.append(unquote(value))
    if values:
        return values
    fallback = request.cookies.get(cookie_name)
    return [fallback] if fallback is not None else []
