import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.utils.security_utils import API_CONTENT_SECURITY_POLICY, HSTS_POLICY, PERMISSIONS_POLICY


@pytest.mark.asyncio
async def test_health_response_includes_hardened_security_headers():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert response.headers["permissions-policy"] == PERMISSIONS_POLICY
    assert response.headers["content-security-policy"] == API_CONTENT_SECURITY_POLICY
    assert response.headers["strict-transport-security"] == HSTS_POLICY
    assert response.headers["x-request-id"]


@pytest.mark.asyncio
async def test_not_found_responses_keep_security_headers():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as client:
        response = await client.get("/api/v1/this-route-does-not-exist")

    assert response.status_code == 404
    assert response.headers["content-security-policy"] == API_CONTENT_SECURITY_POLICY
    assert response.headers["permissions-policy"] == PERMISSIONS_POLICY
    assert response.headers["strict-transport-security"] == HSTS_POLICY
