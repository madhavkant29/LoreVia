"""Compare the deployed frontend and API Git release identities.

Run after both hosts have been promoted:
    python backend/scripts/check_release_pair.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.utils.release_utils import (  # noqa: E402
    UNKNOWN_RELEASE_SHA,
    normalize_release_sha,
)

DEFAULT_FRONTEND_RELEASE_URL = "https://www.getlorevia.com/api/release"
DEFAULT_API_HEALTH_URL = "https://api.getlorevia.com/health"


def release_pair_errors(frontend_payload: Any, api_payload: Any) -> list[str]:
    """Return actionable release-identity errors for two JSON payloads."""
    errors: list[str] = []
    if not isinstance(frontend_payload, dict):
        errors.append("Frontend release endpoint did not return a JSON object")
    if not isinstance(api_payload, dict):
        errors.append("API health endpoint did not return a JSON object")
    if errors:
        return errors

    frontend_sha = normalize_release_sha(frontend_payload.get("release_sha"))
    api_sha = normalize_release_sha(api_payload.get("release_sha"))
    if frontend_sha == UNKNOWN_RELEASE_SHA:
        errors.append("Frontend release SHA is missing or invalid")
    if api_sha == UNKNOWN_RELEASE_SHA:
        errors.append("API release SHA is missing or invalid")
    if not errors and frontend_sha != api_sha:
        errors.append(f"Release mismatch: frontend={frontend_sha} api={api_sha}")
    return errors


def fetch_json(url: str, *, timeout_seconds: float = 10.0) -> Any:
    request = Request(url, headers={"User-Agent": "LoreVia-release-check/1.0"})
    with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
        return json.load(response)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frontend-url", default=DEFAULT_FRONTEND_RELEASE_URL)
    parser.add_argument("--api-url", default=DEFAULT_API_HEALTH_URL)
    args = parser.parse_args()

    try:
        frontend_payload = fetch_json(args.frontend_url)
        api_payload = fetch_json(args.api_url)
    except Exception as exc:
        print(f"Release identity request failed: {type(exc).__name__}", file=sys.stderr)
        return 1

    errors = release_pair_errors(frontend_payload, api_payload)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print(f"Frontend and API release match: {frontend_payload['release_sha'].lower()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
