import pytest
from httpx import ASGITransport, AsyncClient
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from app.utils.tunnel.cloudflare import CloudflareTunnelMiddleware


async def _ok(_request):
    return JSONResponse({"ok": True})


def _app_with_tunnel_middleware() -> Starlette:
    app = Starlette(routes=[Route("/health", _ok), Route("/api", _ok)])
    app.add_middleware(CloudflareTunnelMiddleware)
    return app


@pytest.mark.asyncio
async def test_cloudflare_tunnel_middleware_allows_health_checks_without_cf_headers():
    app = _app_with_tunnel_middleware()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"ok": True}


@pytest.mark.asyncio
async def test_cloudflare_tunnel_middleware_blocks_non_tunnel_requests():
    app = _app_with_tunnel_middleware()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get("/api")

    assert response.status_code == 403
    assert response.json() == {"detail": "Cloudflare tunnel enforcement rejected this request."}


@pytest.mark.asyncio
async def test_cloudflare_tunnel_middleware_rejects_forged_cf_connecting_ip_requests():
    app = _app_with_tunnel_middleware()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get("/api", headers={"CF-Connecting-IP": "203.0.113.11"})

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_cloudflare_tunnel_middleware_allows_sanitized_nginx_requests():
    app = _app_with_tunnel_middleware()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get(
            "/api",
            headers={"CF-Connecting-IP": "203.0.113.11", "X-LoreVia-Edge-Verified": "1"},
        )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
