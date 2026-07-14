from fastapi import HTTPException
from starlette.requests import Request

from app.core.config import settings
from app.utils.admin_security import (
    ADMIN_CSRF_COOKIE_NAME,
    ADMIN_CSRF_HEADER_NAME,
    admin_csrf_allowed_origins,
    create_admin_csrf_token,
    validate_admin_csrf_token,
)


def _request_with_admin_csrf(token: str, origin: str) -> Request:
    cookie = f"{ADMIN_CSRF_COOKIE_NAME}={token}"
    headers = [
        (b"cookie", cookie.encode("utf-8")),
        (ADMIN_CSRF_HEADER_NAME.encode("utf-8"), token.encode("utf-8")),
        (b"origin", origin.encode("utf-8")),
    ]
    return Request({"type": "http", "method": "POST", "headers": headers})


def test_admin_csrf_allowed_origins_include_configured_cors_origins(monkeypatch):
    monkeypatch.setattr(
        settings,
        "BACKEND_CORS_ORIGINS",
        "https://admin.example.com, https://api.example.com, *",
    )
    monkeypatch.setattr(settings, "APP_URL", "https://app.example.com")
    monkeypatch.setattr(settings, "DEBUG", False)

    assert admin_csrf_allowed_origins() >= {
        "https://admin.example.com",
        "https://api.example.com",
        "https://app.example.com",
    }
    assert "*" not in admin_csrf_allowed_origins()


def test_validate_admin_csrf_accepts_configured_frontend_origin(monkeypatch):
    monkeypatch.setattr(settings, "BACKEND_CORS_ORIGINS", "https://admin.example.com")
    monkeypatch.setattr(settings, "APP_URL", "https://app.example.com")
    monkeypatch.setattr(settings, "DEBUG", False)
    token = create_admin_csrf_token()

    validate_admin_csrf_token(_request_with_admin_csrf(token, "https://admin.example.com"))


def test_validate_admin_csrf_rejects_unconfigured_origin(monkeypatch):
    monkeypatch.setattr(settings, "BACKEND_CORS_ORIGINS", "https://admin.example.com")
    monkeypatch.setattr(settings, "APP_URL", "https://app.example.com")
    monkeypatch.setattr(settings, "DEBUG", False)
    token = create_admin_csrf_token()

    try:
        validate_admin_csrf_token(_request_with_admin_csrf(token, "https://evil.example.com"))
    except HTTPException as exc:
        assert exc.status_code == 403
        assert exc.detail == "Invalid admin request origin."
    else:
        raise AssertionError("Expected invalid admin origin to be rejected.")


def test_validate_admin_csrf_rejects_malformed_origin(monkeypatch):
    monkeypatch.setattr(settings, "BACKEND_CORS_ORIGINS", "https://admin.example.com")
    monkeypatch.setattr(settings, "APP_URL", "https://app.example.com")
    monkeypatch.setattr(settings, "DEBUG", False)
    token = create_admin_csrf_token()

    try:
        validate_admin_csrf_token(_request_with_admin_csrf(token, "https://[bad-host"))
    except HTTPException as exc:
        assert exc.status_code == 403
        assert exc.detail == "Invalid admin request origin."
    else:
        raise AssertionError("Expected malformed admin origin to be rejected.")
