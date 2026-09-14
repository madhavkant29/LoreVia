"""Verify the read-only HTTP contract for a public chapter asset origin.

This command never writes or deletes objects.  Use a known-readable public
probe and a known-existing private object key so a denied private response is
meaningful rather than merely proving that an arbitrary key does not exist.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

PUBLIC_PREFIX = "public-assets/"
DENIED_STATUSES = {401, 403, 404}
MAX_AGE_PATTERN = re.compile(r"(?:^|,)\s*max-age\s*=\s*(\d+)\s*(?:,|$)", re.IGNORECASE)


@dataclass(frozen=True)
class OriginProbe:
    status: int
    content_type: str = ""
    cache_control: str = ""


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


def validate_base_url(value: str) -> str:
    base_url = str(value or "").strip().rstrip("/")
    parsed = urlsplit(base_url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("The public asset origin must be an absolute credential-free HTTPS URL.")
    return base_url


def validate_probe_key(value: str, *, public: bool) -> str:
    key = str(value or "").strip().replace("\\", "/").lstrip("/")
    if not key or "//" in key or any(part in {"", ".", ".."} for part in key.split("/")):
        raise ValueError("Probe keys must be non-empty storage keys without traversal segments.")
    if public and not key.startswith(PUBLIC_PREFIX):
        raise ValueError(f"The public probe key must start with {PUBLIC_PREFIX}.")
    if not public and key.startswith(PUBLIC_PREFIX):
        raise ValueError("The private probe key must be outside the public-assets/ prefix.")
    return key


def origin_url(base_url: str, key: str) -> str:
    return f"{validate_base_url(base_url)}/{quote(key, safe='/')}"


def _max_age(cache_control: str) -> int | None:
    match = MAX_AGE_PATTERN.search(str(cache_control or ""))
    return int(match.group(1)) if match else None


def public_asset_origin_errors(
    *,
    public_probe: OriginProbe,
    private_probe: OriginProbe,
    listing_probe: OriginProbe,
    maximum_cache_age: int,
) -> list[str]:
    """Return contract violations from three read-only origin probes."""
    errors: list[str] = []
    if not 200 <= public_probe.status < 300:
        errors.append(f"public probe returned HTTP {public_probe.status}, expected 2xx")
    if not public_probe.content_type.lower().startswith("text/plain"):
        errors.append("public probe is not served as text/plain")
    max_age = _max_age(public_probe.cache_control)
    if max_age is None:
        errors.append("public probe is missing Cache-Control max-age")
    elif max_age > maximum_cache_age:
        errors.append(
            f"public probe max-age {max_age}s exceeds the allowed {maximum_cache_age}s"
        )
    if "must-revalidate" not in public_probe.cache_control.lower():
        errors.append("public probe is missing Cache-Control must-revalidate")
    if private_probe.status not in DENIED_STATUSES:
        errors.append(
            f"known private object returned HTTP {private_probe.status}, expected 401/403/404"
        )
    if listing_probe.status not in DENIED_STATUSES:
        errors.append(
            f"public prefix listing returned HTTP {listing_probe.status}, expected 401/403/404"
        )
    return errors


def probe_url(url: str, *, timeout_seconds: float) -> OriginProbe:
    """Issue a non-redirecting HEAD probe and retain only contract metadata."""
    request = Request(url, method="HEAD", headers={"User-Agent": "LoreVia-origin-preflight/1"})
    opener = build_opener(_NoRedirectHandler())
    try:
        with opener.open(request, timeout=timeout_seconds) as response:
            return OriginProbe(
                status=int(response.status),
                content_type=str(response.headers.get("Content-Type") or ""),
                cache_control=str(response.headers.get("Cache-Control") or ""),
            )
    except HTTPError as exc:
        return OriginProbe(
            status=int(exc.code),
            content_type=str(exc.headers.get("Content-Type") or ""),
            cache_control=str(exc.headers.get("Cache-Control") or ""),
        )
    except (URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"Origin probe failed: {exc}") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default=os.environ.get("PUBLIC_ASSET_BASE_URL"),
        help="HTTPS origin root; defaults to PUBLIC_ASSET_BASE_URL.",
    )
    parser.add_argument("--public-key", required=True, help="Known-readable public-assets/ key.")
    parser.add_argument(
        "--private-key",
        required=True,
        help="Known-existing key outside public-assets/ that the origin must deny.",
    )
    parser.add_argument("--maximum-cache-age", type=int, default=60)
    parser.add_argument("--timeout-seconds", type=float, default=10.0)
    args = parser.parse_args(argv)

    try:
        base_url = validate_base_url(args.base_url)
        public_key = validate_probe_key(args.public_key, public=True)
        private_key = validate_probe_key(args.private_key, public=False)
        maximum_cache_age = max(0, min(int(args.maximum_cache_age), 3600))
        timeout_seconds = max(0.1, min(float(args.timeout_seconds), 60.0))
        public_probe = probe_url(origin_url(base_url, public_key), timeout_seconds=timeout_seconds)
        private_probe = probe_url(origin_url(base_url, private_key), timeout_seconds=timeout_seconds)
        listing_probe = probe_url(
            f"{base_url}/{PUBLIC_PREFIX.rstrip('/')}",
            timeout_seconds=timeout_seconds,
        )
    except (ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    errors = public_asset_origin_errors(
        public_probe=public_probe,
        private_probe=private_probe,
        listing_probe=listing_probe,
        maximum_cache_age=maximum_cache_age,
    )
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("Public asset origin contract passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
