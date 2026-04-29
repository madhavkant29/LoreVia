from starlette.responses import Response

from app.utils.auth_cookies import (
    ACCESS_TOKEN_COOKIE_NAME,
    REFRESH_TOKEN_COOKIE_NAME,
    auth_cookie_secure,
    clear_auth_cookies,
    set_auth_cookies,
)


def test_set_auth_cookies_uses_http_only_lax_path(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.APP_URL", "https://getlorevia.com", raising=False)
    monkeypatch.setattr("app.core.config.settings.DEBUG", False, raising=False)

    response = Response()
    set_auth_cookies(response, "access-token", "refresh-token")

    set_cookie_headers = [
        value.decode() if isinstance(value, bytes) else value
        for name, value in response.raw_headers
        if name.lower() == b"set-cookie"
    ]
    assert any(ACCESS_TOKEN_COOKIE_NAME in header for header in set_cookie_headers)
    assert any(REFRESH_TOKEN_COOKIE_NAME in header for header in set_cookie_headers)
    assert any("httponly" in header.lower() for header in set_cookie_headers)
    assert any("samesite=lax" in header.lower() for header in set_cookie_headers)
    assert any("secure" in header.lower() for header in set_cookie_headers)
    assert any("path=/api/v1" in header.lower() for header in set_cookie_headers)


def test_set_auth_cookies_disables_secure_for_local_http(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.APP_URL", "http://localhost:3000", raising=False)
    monkeypatch.setattr("app.core.config.settings.DEBUG", True, raising=False)

    response = Response()
    set_auth_cookies(response, "access-token", "refresh-token")

    set_cookie_headers = [
        value.decode() if isinstance(value, bytes) else value
        for name, value in response.raw_headers
        if name.lower() == b"set-cookie"
    ]
    assert all("secure" not in header.lower() for header in set_cookie_headers)
    assert auth_cookie_secure() is False


def test_clear_auth_cookies_sets_expired_headers(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.APP_URL", "https://getlorevia.com", raising=False)
    monkeypatch.setattr("app.core.config.settings.DEBUG", False, raising=False)

    response = Response()
    clear_auth_cookies(response)

    set_cookie_headers = [
        value.decode() if isinstance(value, bytes) else value
        for name, value in response.raw_headers
        if name.lower() == b"set-cookie"
    ]
    assert len(set_cookie_headers) == 2
    assert any(ACCESS_TOKEN_COOKIE_NAME in header for header in set_cookie_headers)
    assert any(REFRESH_TOKEN_COOKIE_NAME in header for header in set_cookie_headers)
