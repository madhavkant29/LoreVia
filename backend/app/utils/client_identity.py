from __future__ import annotations

import hmac
import ipaddress

from fastapi import Request

from app.core.config import settings

EDGE_VERIFIED_HEADER = "x-lorevia-edge-verified"
EDGE_VERIFIED_VALUE = "1"
EDGE_TOKEN_HEADER = "x-lorevia-edge-token"

_TRUSTED_PROXY_NETS = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
)


def parse_client_ip(value: str | None) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.startswith("[") and "]" in raw:
        raw = raw[1 : raw.index("]")]
    try:
        parsed = ipaddress.ip_address(raw)
    except ValueError:
        return None
    return str(parsed)


def _direct_client_ip(request: Request) -> str | None:
    if request.client is None:
        return None
    return parse_client_ip(request.client.host)


def direct_peer_is_trusted_proxy(request: Request) -> bool:
    direct_ip = _direct_client_ip(request)
    if direct_ip is None:
        return False
    parsed = ipaddress.ip_address(direct_ip)
    return any(parsed in network for network in _TRUSTED_PROXY_NETS)


def edge_verification_present(request: Request) -> bool:
    return edge_verification_values_match(
        request.headers.get(EDGE_VERIFIED_HEADER),
        request.headers.get(EDGE_TOKEN_HEADER),
    )


def edge_verification_values_match(marker: str | None, token: str | None) -> bool:
    if marker != EDGE_VERIFIED_VALUE:
        return False
    expected_token = settings.resolved_edge_proxy_secret()
    if not expected_token:
        # Preserve local/test ergonomics, but never permit marker-only trust when
        # production validation has been bypassed or settings were monkeypatched.
        return settings.DEPLOYMENT_ENV != "production"
    return bool(token) and hmac.compare_digest(str(token), expected_token)


def _first_forwarded_ip(header_value: str | None) -> str | None:
    for candidate in str(header_value or "").split(","):
        parsed = parse_client_ip(candidate)
        if parsed is not None:
            return parsed
    return None


def trusted_client_ip(request: Request | None) -> str | None:
    if request is None:
        return None
    direct_ip = _direct_client_ip(request)
    if not direct_peer_is_trusted_proxy(request) or not edge_verification_present(request):
        return direct_ip

    for header_name in ("cf-connecting-ip", "x-real-ip", "x-forwarded-for"):
        header_ip = _first_forwarded_ip(request.headers.get(header_name))
        if header_ip is not None:
            return header_ip
    return direct_ip


def trusted_client_identifier(request: Request | None) -> str:
    return trusted_client_ip(request) or "unknown"
