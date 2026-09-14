"""Verify LoreVia's public, read-only cross-host release boundaries.

This command sends unauthenticated GET and CORS preflight requests only. It
does not log in, submit content, call webhooks, or mutate application data.

Run after the frontend and API candidates have both been promoted:
    python backend/scripts/check_public_release_boundaries.py
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts.check_release_pair import release_pair_errors  # noqa: E402

DEFAULT_FRONTEND_ORIGIN = "https://www.getlorevia.com"
DEFAULT_API_ORIGIN = "https://api.getlorevia.com"
MAX_RESPONSE_BYTES = 1024 * 1024
REQUIRED_SECURITY_HEADERS = frozenset(
    {
        "content-security-policy",
        "permissions-policy",
        "referrer-policy",
        "strict-transport-security",
        "x-content-type-options",
        "x-frame-options",
    }
)


@dataclass(frozen=True)
class HttpObservation:
    requested_url: str
    final_url: str
    status: int
    headers: Mapping[str, str]
    body: bytes

    def json_payload(self) -> Any:
        try:
            return json.loads(self.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None


def normalized_https_origin(value: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme.casefold() != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise ValueError("Release boundary origins must be credential-free HTTPS origins.")
    host = parsed.hostname.casefold()
    if ":" in host:
        host = f"[{host}]"
    authority = f"{host}:{parsed.port}" if parsed.port else host
    return f"https://{authority}"


def fetch_observation(
    url: str,
    *,
    method: str = "GET",
    headers: Mapping[str, str] | None = None,
    timeout_seconds: float = 10.0,
) -> HttpObservation:
    if urlsplit(url).scheme.casefold() != "https":
        raise ValueError("Release boundary requests require HTTPS.")
    request_headers = {
        "Accept": "application/json, text/html;q=0.9",
        "User-Agent": "LoreVia-public-release-check/1.0",
        **dict(headers or {}),
    }
    request = Request(url, headers=request_headers, method=method)
    try:
        response = urlopen(request, timeout=timeout_seconds)  # noqa: S310
    except HTTPError as exc:
        response = exc
    try:
        body = response.read(MAX_RESPONSE_BYTES + 1)
        if len(body) > MAX_RESPONSE_BYTES:
            raise ValueError("Release boundary response exceeded the 1 MiB safety limit.")
        return HttpObservation(
            requested_url=url,
            final_url=response.geturl(),
            status=int(response.status),
            headers={key.casefold(): value.strip() for key, value in response.headers.items()},
            body=body,
        )
    finally:
        response.close()


def collect_public_boundaries(
    frontend_origin: str,
    api_origin: str,
    *,
    timeout_seconds: float = 10.0,
    fetcher: Callable[..., HttpObservation] = fetch_observation,
) -> dict[str, HttpObservation]:
    frontend_origin = normalized_https_origin(frontend_origin)
    api_origin = normalized_https_origin(api_origin)
    cors_headers = {"Access-Control-Request-Method": "GET"}
    return {
        "frontend_home": fetcher(f"{frontend_origin}/", timeout_seconds=timeout_seconds),
        "frontend_release": fetcher(
            f"{frontend_origin}/api/release", timeout_seconds=timeout_seconds
        ),
        "api_health": fetcher(f"{api_origin}/health", timeout_seconds=timeout_seconds),
        "api_ready": fetcher(f"{api_origin}/ready", timeout_seconds=timeout_seconds),
        "private_page": fetcher(f"{frontend_origin}/library", timeout_seconds=timeout_seconds),
        "direct_anonymous_books": fetcher(
            f"{api_origin}/api/v1/books/", timeout_seconds=timeout_seconds
        ),
        "proxied_anonymous_books": fetcher(
            f"{frontend_origin}/api/v1/books/", timeout_seconds=timeout_seconds
        ),
        "untrusted_cors": fetcher(
            f"{api_origin}/api/v1/books/",
            method="OPTIONS",
            headers={"Origin": "https://cross-origin.invalid", **cors_headers},
            timeout_seconds=timeout_seconds,
        ),
        "trusted_cors": fetcher(
            f"{api_origin}/api/v1/books/",
            method="OPTIONS",
            headers={"Origin": frontend_origin, **cors_headers},
            timeout_seconds=timeout_seconds,
        ),
    }


def public_boundary_errors(
    observations: Mapping[str, HttpObservation],
    *,
    frontend_origin: str,
    api_origin: str,
) -> list[str]:
    frontend_origin = normalized_https_origin(frontend_origin)
    normalized_https_origin(api_origin)
    errors: list[str] = []
    expected_statuses = {
        "frontend_home": 200,
        "frontend_release": 200,
        "api_health": 200,
        "api_ready": 200,
        "private_page": 200,
        "direct_anonymous_books": 401,
        "proxied_anonymous_books": 401,
        "untrusted_cors": 400,
        "trusted_cors": 200,
    }
    missing = sorted(set(expected_statuses) - set(observations))
    if missing:
        errors.append("Missing release observations: " + ", ".join(missing))
        return errors

    for name, expected_status in expected_statuses.items():
        actual_status = observations[name].status
        if actual_status != expected_status:
            errors.append(f"{name} returned HTTP {actual_status}; expected {expected_status}")

    private_final = urlsplit(observations["private_page"].final_url)
    private_final_origin = f"{private_final.scheme}://{private_final.netloc}".casefold()
    if private_final_origin != frontend_origin.casefold() or private_final.path != "/login":
        errors.append("Anonymous private page did not finish on the frontend /login route")

    frontend_release = observations["frontend_release"].json_payload()
    api_health = observations["api_health"].json_payload()
    errors.extend(release_pair_errors(frontend_release, api_health))
    api_ready = observations["api_ready"].json_payload()
    if not isinstance(api_ready, dict) or api_ready.get("status") != "ready":
        errors.append("API readiness endpoint did not return ready JSON")

    for name in ("frontend_release", "api_health", "api_ready"):
        observation = observations[name]
        if "application/json" not in observation.headers.get("content-type", "").casefold():
            errors.append(f"{name} did not return an application/json content type")
        if "no-store" not in observation.headers.get("cache-control", "").casefold():
            errors.append(f"{name} did not return a no-store cache policy")

    for name in ("frontend_home", "api_health"):
        headers = observations[name].headers
        missing_headers = sorted(REQUIRED_SECURITY_HEADERS - set(headers))
        if missing_headers:
            errors.append(f"{name} is missing security headers: {', '.join(missing_headers)}")
        if headers.get("x-frame-options", "").casefold() != "deny":
            errors.append(f"{name} does not deny framing")
        if headers.get("x-content-type-options", "").casefold() != "nosniff":
            errors.append(f"{name} does not disable MIME sniffing")

    untrusted_headers = observations["untrusted_cors"].headers
    if "access-control-allow-origin" in untrusted_headers:
        errors.append("Untrusted CORS preflight received an allow-origin header")
    trusted_headers = observations["trusted_cors"].headers
    if (
        trusted_headers.get("access-control-allow-origin", "").casefold()
        != frontend_origin.casefold()
    ):
        errors.append("Trusted CORS preflight did not allow the frontend origin")
    if trusted_headers.get("access-control-allow-credentials", "").casefold() != "true":
        errors.append("Trusted CORS preflight did not allow credentialed requests")
    return errors


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frontend-origin", default=DEFAULT_FRONTEND_ORIGIN)
    parser.add_argument("--api-origin", default=DEFAULT_API_ORIGIN)
    parser.add_argument("--timeout-seconds", type=float, default=10.0)
    args = parser.parse_args(argv)
    try:
        observations = collect_public_boundaries(
            args.frontend_origin,
            args.api_origin,
            timeout_seconds=max(1.0, min(args.timeout_seconds, 60.0)),
        )
        errors = public_boundary_errors(
            observations,
            frontend_origin=args.frontend_origin,
            api_origin=args.api_origin,
        )
    except Exception as exc:
        print(f"Public release boundary check failed: {type(exc).__name__}", file=sys.stderr)
        return 1
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    release_sha = observations["frontend_release"].json_payload()["release_sha"]
    print(f"Public release boundaries passed for release {release_sha.lower()}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
