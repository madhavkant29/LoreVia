import pytest
from fastapi import HTTPException
from starlette.requests import Request
from starlette.responses import Response

from app.core.security import create_access_token
from app.utils.auth_cookies import (
    ACCESS_TOKEN_COOKIE_NAME,
    DEVICE_ID_COOKIE_NAME,
    REFRESH_TOKEN_COOKIE_NAME,
    auth_cookie_secure,
    clear_auth_cookies,
    get_auth_token,
    get_device_cookie,
    resolve_device_id,
    set_access_cookie,
    set_auth_cookies,
    set_device_cookie,
)
from app.utils.auth_csrf import (
    AUTH_CSRF_COOKIE_NAME,
    AUTH_CSRF_HEADER_NAME,
    _has_valid_bearer_access_token,
    cookie_authenticated_request_requires_csrf,
    create_auth_csrf_token,
    set_auth_csrf_cookie,
    validate_auth_csrf_token,
)
from app.utils.cookie_utils import auth_cookie_domain


def test_set_auth_cookies_uses_http_only_lax_path(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.APP_URL", "https://getlorevia.com", raising=False)
    monkeypatch.setattr("app.core.config.settings.AUTH_COOKIE_DOMAIN", None, raising=False)
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
    assert any(AUTH_CSRF_COOKIE_NAME in header for header in set_cookie_headers)
    assert any("httponly" in header.lower() for header in set_cookie_headers)
    assert any("samesite=lax" in header.lower() for header in set_cookie_headers)
    assert any("secure" in header.lower() for header in set_cookie_headers)
    assert any("path=/" in header.lower() for header in set_cookie_headers)
    assert all("domain=" not in header.lower() for header in set_cookie_headers)


def test_auth_cookie_domain_requires_explicit_matching_override(monkeypatch):
    monkeypatch.setattr(
        "app.core.config.settings.APP_URL", "https://app.getlorevia.com", raising=False
    )

    monkeypatch.setattr("app.core.config.settings.AUTH_COOKIE_DOMAIN", None, raising=False)
    assert auth_cookie_domain() is None

    monkeypatch.setattr(
        "app.core.config.settings.AUTH_COOKIE_DOMAIN", ".getlorevia.com", raising=False
    )
    assert auth_cookie_domain() == "getlorevia.com"

    monkeypatch.setattr("app.core.config.settings.AUTH_COOKIE_DOMAIN", "example.com", raising=False)
    assert auth_cookie_domain() is None

    monkeypatch.setattr("app.core.config.settings.APP_URL", "https://[bad-host", raising=False)
    monkeypatch.setattr(
        "app.core.config.settings.AUTH_COOKIE_DOMAIN", ".getlorevia.com", raising=False
    )
    assert auth_cookie_domain() is None


def test_set_auth_cookies_expires_legacy_api_prefix_cookies(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.API_V1_PREFIX", "/api/v1", raising=False)
    monkeypatch.setattr("app.core.config.settings.APP_URL", "https://getlorevia.com", raising=False)
    monkeypatch.setattr("app.core.config.settings.DEBUG", False, raising=False)

    response = Response()
    set_auth_cookies(response, "access-token", "refresh-token")

    set_cookie_headers = [
        value.decode() if isinstance(value, bytes) else value
        for name, value in response.raw_headers
        if name.lower() == b"set-cookie"
    ]
    assert any(
        ACCESS_TOKEN_COOKIE_NAME in header and "path=/api/v1" in header.lower()
        for header in set_cookie_headers
    )
    assert any(
        ACCESS_TOKEN_COOKIE_NAME in header and "path=/api/v1/" in header.lower()
        for header in set_cookie_headers
    )
    assert any(
        REFRESH_TOKEN_COOKIE_NAME in header and "path=/api/v1" in header.lower()
        for header in set_cookie_headers
    )
    assert any(
        REFRESH_TOKEN_COOKIE_NAME in header and "path=/api/v1/" in header.lower()
        for header in set_cookie_headers
    )
    assert any(
        AUTH_CSRF_COOKIE_NAME in header and "path=/api/v1" in header.lower()
        for header in set_cookie_headers
    )
    assert any(
        AUTH_CSRF_COOKIE_NAME in header and "path=/api/v1/" in header.lower()
        for header in set_cookie_headers
    )


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


def test_auth_cookie_secure_cannot_be_downgraded_by_production_app_url(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.APP_URL", "http://getlorevia.com", raising=False)
    monkeypatch.setattr("app.core.config.settings.DEBUG", False, raising=False)

    assert auth_cookie_secure() is True


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
    assert any(ACCESS_TOKEN_COOKIE_NAME in header for header in set_cookie_headers)
    assert any(REFRESH_TOKEN_COOKIE_NAME in header for header in set_cookie_headers)
    assert any(AUTH_CSRF_COOKIE_NAME in header for header in set_cookie_headers)
    assert any("path=/" in header.lower() for header in set_cookie_headers)


def test_set_access_cookie_sets_only_the_access_token(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.APP_URL", "https://getlorevia.com", raising=False)
    monkeypatch.setattr("app.core.config.settings.DEBUG", False, raising=False)

    response = Response()
    set_access_cookie(response, "access-token")

    set_cookie_headers = [
        value.decode() if isinstance(value, bytes) else value
        for name, value in response.raw_headers
        if name.lower() == b"set-cookie"
    ]
    active_access_cookie = next(
        header
        for header in set_cookie_headers
        if ACCESS_TOKEN_COOKIE_NAME in header and "max-age=900" in header.lower()
    )
    assert "httponly" in active_access_cookie.lower()
    assert "samesite=lax" in active_access_cookie.lower()
    assert "path=/" in active_access_cookie.lower()
    assert any(AUTH_CSRF_COOKIE_NAME in header for header in set_cookie_headers)


def test_set_access_cookie_expires_legacy_api_prefix_access_cookie(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.API_V1_PREFIX", "/api/v1", raising=False)
    monkeypatch.setattr("app.core.config.settings.APP_URL", "https://getlorevia.com", raising=False)
    monkeypatch.setattr("app.core.config.settings.DEBUG", False, raising=False)

    response = Response()
    set_access_cookie(response, "access-token")

    set_cookie_headers = [
        value.decode() if isinstance(value, bytes) else value
        for name, value in response.raw_headers
        if name.lower() == b"set-cookie"
    ]
    assert any(
        ACCESS_TOKEN_COOKIE_NAME in header and "path=/api/v1" in header.lower()
        for header in set_cookie_headers
    )
    assert any(
        ACCESS_TOKEN_COOKIE_NAME in header and "path=/api/v1/" in header.lower()
        for header in set_cookie_headers
    )
    assert any(
        AUTH_CSRF_COOKIE_NAME in header and "path=/api/v1" in header.lower()
        for header in set_cookie_headers
    )
    assert any(
        AUTH_CSRF_COOKIE_NAME in header and "path=/api/v1/" in header.lower()
        for header in set_cookie_headers
    )


def test_set_device_cookie_uses_http_only_lax_path(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.APP_URL", "https://getlorevia.com", raising=False)
    monkeypatch.setattr("app.core.config.settings.DEBUG", False, raising=False)

    response = Response()
    set_device_cookie(response, "device-cookie-id01")

    set_cookie_headers = [
        value.decode() if isinstance(value, bytes) else value
        for name, value in response.raw_headers
        if name.lower() == b"set-cookie"
    ]
    active_device_cookie = next(
        header
        for header in set_cookie_headers
        if DEVICE_ID_COOKIE_NAME in header and "device-cookie-id01" in header
    )
    assert "httponly" in active_device_cookie.lower()
    assert "samesite=lax" in active_device_cookie.lower()
    assert "path=/" in active_device_cookie.lower()


def test_resolve_device_id_prefers_cookie_over_request_payload():
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "headers": [(b"cookie", b"lorevia_device_id=device-cookie-id01")],
        }
    )

    assert get_device_cookie(request) == "device-cookie-id01"
    assert resolve_device_id(request, "request-device-id02") == "device-cookie-id01"


def test_resolve_device_id_uses_request_payload_when_cookie_missing():
    request = Request({"type": "http", "method": "POST", "headers": []})

    assert resolve_device_id(request, "request-device-id02") == "request-device-id02"


def test_resolve_device_id_requires_cookie_or_request_payload():
    request = Request({"type": "http", "method": "POST", "headers": []})

    with pytest.raises(ValueError, match="Device identifier is required."):
        resolve_device_id(request, None)


def test_set_auth_csrf_cookie_uses_readable_lax_cookie(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.APP_URL", "https://getlorevia.com", raising=False)
    monkeypatch.setattr("app.core.config.settings.DEBUG", False, raising=False)

    response = Response()
    set_auth_csrf_cookie(response, "csrf-token")

    set_cookie_headers = [
        value.decode() if isinstance(value, bytes) else value
        for name, value in response.raw_headers
        if name.lower() == b"set-cookie"
    ]
    active_csrf_cookie = next(
        header
        for header in set_cookie_headers
        if AUTH_CSRF_COOKIE_NAME in header and "csrf-token" in header
    )
    assert "httponly" not in active_csrf_cookie.lower()
    assert "samesite=lax" in active_csrf_cookie.lower()
    assert "path=/" in active_csrf_cookie.lower()


def test_cookie_authenticated_request_requires_csrf_only_for_unsafe_requests_without_valid_bearer():
    patch_request = Request({"type": "http", "method": "PATCH", "headers": []})
    get_request = Request({"type": "http", "method": "GET", "headers": []})
    forged_bearer_request = Request(
        {"type": "http", "method": "POST", "headers": [(b"authorization", b"Bearer token")]}
    )
    valid_bearer = create_access_token("user-1")
    bearer_request = Request(
        {
            "type": "http",
            "method": "POST",
            "headers": [(b"authorization", f"Bearer {valid_bearer}".encode())],
        }
    )

    assert cookie_authenticated_request_requires_csrf(patch_request) is True
    assert cookie_authenticated_request_requires_csrf(get_request) is False
    assert cookie_authenticated_request_requires_csrf(forged_bearer_request) is True
    assert cookie_authenticated_request_requires_csrf(bearer_request) is False


def test_get_auth_token_prefers_cookie_over_bearer_token():
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "headers": [(b"cookie", b"lorevia_access_token=cookie-token")],
        }
    )

    assert get_auth_token(request, bearer_token="bearer-token") == "cookie-token"


def test_get_auth_token_prefers_last_duplicate_cookie_value():
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "headers": [
                (
                    b"cookie",
                    b"lorevia_access_token=stale-token; lorevia_access_token=fresh-token",
                )
            ],
        }
    )

    assert get_auth_token(request, bearer_token="bearer-token") == "fresh-token"


def test_get_auth_token_uses_bearer_token_when_cookie_is_missing():
    request = Request({"type": "http", "method": "GET", "headers": []})

    assert get_auth_token(request, bearer_token="bearer-token") == "bearer-token"


def test_validate_auth_csrf_token_accepts_matching_cookie_header_and_origin():
    token = create_auth_csrf_token()
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "headers": [
                (b"cookie", f"{AUTH_CSRF_COOKIE_NAME}={token}".encode()),
                (AUTH_CSRF_HEADER_NAME.encode("utf-8"), token.encode("utf-8")),
                (b"origin", b"https://getlorevia.com"),
            ],
        }
    )

    validate_auth_csrf_token(request)


def test_validate_auth_csrf_token_prefers_last_duplicate_cookie_value():
    stale_token = create_auth_csrf_token()
    fresh_token = create_auth_csrf_token()
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "headers": [
                (
                    b"cookie",
                    f"{AUTH_CSRF_COOKIE_NAME}={stale_token}; {AUTH_CSRF_COOKIE_NAME}={fresh_token}".encode(),
                ),
                (AUTH_CSRF_HEADER_NAME.encode("utf-8"), fresh_token.encode("utf-8")),
                (b"origin", b"https://getlorevia.com"),
            ],
        }
    )

    validate_auth_csrf_token(request)


@pytest.mark.parametrize(
    ("cookie_token", "header_token", "origin"),
    [
        (None, "token", "https://getlorevia.com"),
        ("token", None, "https://getlorevia.com"),
        ("token", "different", "https://getlorevia.com"),
        (create_auth_csrf_token(), create_auth_csrf_token(), "https://evil.example"),
    ],
)
def test_validate_auth_csrf_token_rejects_invalid_inputs(cookie_token, header_token, origin):
    headers = []
    if cookie_token:
        headers.append((b"cookie", f"{AUTH_CSRF_COOKIE_NAME}={cookie_token}".encode()))
    if header_token:
        headers.append((AUTH_CSRF_HEADER_NAME.encode("utf-8"), header_token.encode("utf-8")))
    if origin:
        headers.append((b"origin", origin.encode("utf-8")))
    request = Request({"type": "http", "method": "POST", "headers": headers})

    with pytest.raises(HTTPException) as exc_info:
        validate_auth_csrf_token(request)

    assert exc_info.value.status_code == 403


def test_validate_auth_csrf_token_rejects_malformed_origin():
    token = create_auth_csrf_token()
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "headers": [
                (b"cookie", f"{AUTH_CSRF_COOKIE_NAME}={token}".encode()),
                (AUTH_CSRF_HEADER_NAME.encode("utf-8"), token.encode("utf-8")),
                (b"origin", b"https://[bad-host"),
            ],
        }
    )

    with pytest.raises(HTTPException) as exc_info:
        validate_auth_csrf_token(request)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Invalid request origin."


def test_has_valid_bearer_access_token_propagates_unexpected_decode_errors(monkeypatch):
    def fake_decode(_token: str):
        raise RuntimeError("programming error")

    monkeypatch.setattr("app.utils.auth_csrf.decode_token", fake_decode)

    with pytest.raises(RuntimeError, match="programming error"):
        _has_valid_bearer_access_token("Bearer token")
