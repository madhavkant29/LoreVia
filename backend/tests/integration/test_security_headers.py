import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import allowed_hosts
from app.main import app
from app.utils.security_utils import API_CONTENT_SECURITY_POLICY, HSTS_POLICY, PERMISSIONS_POLICY


def _trusted_base_url() -> str:
    hosts = allowed_hosts()
    for preferred in ("localhost", "127.0.0.1"):
        if preferred in hosts:
            return f"http://{preferred}"
    if hosts:
        return f"https://{hosts[0]}"
    return "http://localhost"


@pytest.mark.asyncio
async def test_health_response_includes_hardened_security_headers(monkeypatch):
    monkeypatch.setattr("app.main.settings.RELEASE_SHA", "A" * 40, raising=False)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url=_trusted_base_url()
    ) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json()["release_sha"] == "a" * 40
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert response.headers["permissions-policy"] == PERMISSIONS_POLICY
    assert response.headers["content-security-policy"] == API_CONTENT_SECURITY_POLICY
    assert response.headers["strict-transport-security"] == HSTS_POLICY


@pytest.mark.asyncio
async def test_private_api_errors_are_not_shared_cacheable():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url=_trusted_base_url()
    ) as client:
        response = await client.get("/api/v1/books")

    assert response.status_code == 401
    assert response.headers["cache-control"] == (
        "private, no-store, no-cache, max-age=0, must-revalidate"
    )
    assert response.headers["x-request-id"]


@pytest.mark.asyncio
async def test_not_found_responses_keep_security_headers():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url=_trusted_base_url()
    ) as client:
        response = await client.get("/api/v1/this-route-does-not-exist")

    assert response.status_code == 404
    assert response.headers["content-security-policy"] == API_CONTENT_SECURITY_POLICY
    assert response.headers["permissions-policy"] == PERMISSIONS_POLICY
    assert response.headers["strict-transport-security"] == HSTS_POLICY


@pytest.mark.asyncio
async def test_health_allows_localhost_with_port_in_debug_mode():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://localhost:8000"
    ) as client:
        response = await client.get("/health")

    assert response.status_code == 200
