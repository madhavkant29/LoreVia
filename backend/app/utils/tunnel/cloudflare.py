"""
Cloudflare Tunnel request enforcement helpers.

When Cloudflare Tunnel is enabled, public application traffic should arrive
through Cloudflare and include tunnel-managed headers such as
``CF-Connecting-IP``. This middleware rejects ordinary application requests
that do not include those headers while still allowing platform health checks.
"""

from __future__ import annotations

import ipaddress

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.utils.client_identity import edge_verification_values_match

_HEALTHCHECK_PATHS = frozenset({"/health", "/ready"})
_TRUSTED_EDGE_PROXY_NETS = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
)


class CloudflareTunnelMiddleware:
    """Reject direct origin traffic when tunnel enforcement is enabled."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path in _HEALTHCHECK_PATHS:
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        direct_client = scope.get("client")
        direct_host = direct_client[0] if direct_client else ""
        if (
            not _is_trusted_edge_proxy(direct_host)
            or not edge_verification_values_match(
                _header_text(headers.get(b"x-lorevia-edge-verified")),
                _header_text(headers.get(b"x-lorevia-edge-token")),
            )
            or b"cf-connecting-ip" not in headers
        ):
            response = JSONResponse(
                status_code=403,
                content={"detail": "Cloudflare tunnel enforcement rejected this request."},
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)


def _header_text(value: bytes | None) -> str | None:
    if value is None:
        return None
    try:
        return value.decode("ascii")
    except UnicodeDecodeError:
        return None


def _is_trusted_edge_proxy(host: str) -> bool:
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return any(address in network for network in _TRUSTED_EDGE_PROXY_NETS)
