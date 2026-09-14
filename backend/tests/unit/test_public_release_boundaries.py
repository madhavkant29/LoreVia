from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.error import HTTPError

import pytest

from scripts import check_public_release_boundaries
from scripts.check_public_release_boundaries import (
    HttpObservation,
    collect_public_boundaries,
    fetch_observation,
    normalized_https_origin,
    public_boundary_errors,
)

RELEASE_SHA = "a" * 40
SECURITY_HEADERS = {
    "content-security-policy": "default-src 'none'",
    "permissions-policy": "camera=()",
    "referrer-policy": "strict-origin-when-cross-origin",
    "strict-transport-security": "max-age=31536000",
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
}


def _observation(
    url: str,
    *,
    status: int = 200,
    headers: Mapping[str, str] | None = None,
    payload: Any = None,
) -> HttpObservation:
    body = b"" if payload is None else check_public_release_boundaries.json.dumps(payload).encode()
    return HttpObservation(
        requested_url=url,
        final_url=url,
        status=status,
        headers=dict(headers or {}),
        body=body,
    )


def _passing_observations() -> dict[str, HttpObservation]:
    json_headers = {
        **SECURITY_HEADERS,
        "content-type": "application/json",
        "cache-control": "no-store",
    }
    observations = {
        "frontend_home": _observation("https://www.getlorevia.com/", headers=SECURITY_HEADERS),
        "frontend_release": _observation(
            "https://www.getlorevia.com/api/release",
            headers=json_headers,
            payload={"release_sha": RELEASE_SHA},
        ),
        "api_health": _observation(
            "https://api.getlorevia.com/health",
            headers=json_headers,
            payload={"release_sha": RELEASE_SHA},
        ),
        "api_ready": _observation(
            "https://api.getlorevia.com/ready",
            headers=json_headers,
            payload={"status": "ready"},
        ),
        "private_page": _observation("https://www.getlorevia.com/login"),
        "direct_anonymous_books": _observation(
            "https://api.getlorevia.com/api/v1/books/", status=401
        ),
        "proxied_anonymous_books": _observation(
            "https://www.getlorevia.com/api/v1/books/", status=401
        ),
        "untrusted_cors": _observation("https://api.getlorevia.com/api/v1/books/", status=400),
        "trusted_cors": _observation(
            "https://api.getlorevia.com/api/v1/books/",
            headers={
                "access-control-allow-origin": "https://www.getlorevia.com",
                "access-control-allow-credentials": "true",
            },
        ),
    }
    return observations


def test_public_boundary_contract_accepts_secure_matching_hosts() -> None:
    assert (
        public_boundary_errors(
            _passing_observations(),
            frontend_origin="https://www.getlorevia.com",
            api_origin="https://api.getlorevia.com",
        )
        == []
    )


def test_public_boundary_contract_reports_auth_cors_cache_and_release_failures() -> None:
    observations = _passing_observations()
    observations["frontend_release"] = _observation(
        "https://www.getlorevia.com/api/release",
        headers={"content-type": "text/plain"},
        payload={"release_sha": "b" * 40},
    )
    observations["direct_anonymous_books"] = _observation(
        "https://api.getlorevia.com/api/v1/books/", status=200
    )
    observations["untrusted_cors"] = _observation(
        "https://api.getlorevia.com/api/v1/books/",
        status=200,
        headers={"access-control-allow-origin": "https://cross-origin.invalid"},
    )

    errors = public_boundary_errors(
        observations,
        frontend_origin="https://www.getlorevia.com",
        api_origin="https://api.getlorevia.com",
    )

    assert f"Release mismatch: frontend={'b' * 40} api={RELEASE_SHA}" in errors
    assert "direct_anonymous_books returned HTTP 200; expected 401" in errors
    assert "untrusted_cors returned HTTP 200; expected 400" in errors
    assert "Untrusted CORS preflight received an allow-origin header" in errors
    assert "frontend_release did not return an application/json content type" in errors
    assert "frontend_release did not return a no-store cache policy" in errors


def test_public_boundary_contract_reports_missing_observations_without_key_errors() -> None:
    observations = _passing_observations()
    del observations["api_ready"]

    assert public_boundary_errors(
        observations,
        frontend_origin="https://www.getlorevia.com",
        api_origin="https://api.getlorevia.com",
    ) == ["Missing release observations: api_ready"]


def test_public_boundary_contract_rejects_redirect_readiness_and_header_regressions() -> None:
    observations = _passing_observations()
    observations["private_page"] = _observation("https://www.getlorevia.com/library")
    observations["api_ready"] = _observation(
        "https://api.getlorevia.com/ready",
        headers={"content-type": "application/json", "cache-control": "no-store"},
        payload={"status": "degraded"},
    )
    observations["frontend_home"] = _observation(
        "https://www.getlorevia.com/",
        headers={"x-frame-options": "SAMEORIGIN", "x-content-type-options": "text/plain"},
    )
    observations["trusted_cors"] = _observation(
        "https://api.getlorevia.com/api/v1/books/",
        headers={"access-control-allow-origin": "https://other.invalid"},
    )

    errors = public_boundary_errors(
        observations,
        frontend_origin="https://www.getlorevia.com",
        api_origin="https://api.getlorevia.com",
    )

    assert "Anonymous private page did not finish on the frontend /login route" in errors
    assert "API readiness endpoint did not return ready JSON" in errors
    assert any(error.startswith("frontend_home is missing security headers:") for error in errors)
    assert "frontend_home does not deny framing" in errors
    assert "frontend_home does not disable MIME sniffing" in errors
    assert "Trusted CORS preflight did not allow the frontend origin" in errors
    assert "Trusted CORS preflight did not allow credentialed requests" in errors


@pytest.mark.parametrize(
    "value",
    [
        "http://www.getlorevia.com",
        "https://user:secret@www.getlorevia.com",
        "https://www.getlorevia.com/path",
        "https://www.getlorevia.com?query=1",
    ],
)
def test_origin_normalization_rejects_unsafe_or_non_origin_values(value: str) -> None:
    with pytest.raises(ValueError, match="credential-free HTTPS origins"):
        normalized_https_origin(value)


def test_collect_public_boundaries_issues_only_expected_read_requests() -> None:
    calls: list[tuple[str, str, dict[str, str]]] = []

    def fetcher(
        url: str,
        *,
        method: str = "GET",
        headers: Mapping[str, str] | None = None,
        timeout_seconds: float,
    ) -> HttpObservation:
        assert timeout_seconds == 7.0
        calls.append((url, method, dict(headers or {})))
        return _observation(url)

    observations = collect_public_boundaries(
        "https://www.getlorevia.com/",
        "https://api.getlorevia.com",
        timeout_seconds=7.0,
        fetcher=fetcher,
    )

    assert set(observations) == {
        "frontend_home",
        "frontend_release",
        "api_health",
        "api_ready",
        "private_page",
        "direct_anonymous_books",
        "proxied_anonymous_books",
        "untrusted_cors",
        "trusted_cors",
    }
    assert sum(method == "GET" for _, method, _ in calls) == 7
    assert sum(method == "OPTIONS" for _, method, _ in calls) == 2
    assert all(method in {"GET", "OPTIONS"} for _, method, _ in calls)


class _Headers:
    def items(self) -> list[tuple[str, str]]:
        return [("Content-Type", "application/json")]


class _Response:
    status = 401
    headers = _Headers()

    def __init__(self, body: bytes = b'{"detail":"unauthorized"}') -> None:
        self.body = body
        self.closed = False

    def read(self, _limit: int) -> bytes:
        return self.body

    def geturl(self) -> str:
        return "https://api.getlorevia.com/api/v1/books/"

    def close(self) -> None:
        self.closed = True


def test_fetch_observation_records_http_error_without_exposing_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = _Response()
    error = HTTPError(response.geturl(), 401, "unauthorized", response.headers, response)
    monkeypatch.setattr(
        check_public_release_boundaries,
        "urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(error),
    )

    observation = fetch_observation(response.geturl())

    assert observation.status == 401
    assert observation.json_payload() == {"detail": "unauthorized"}
    assert response.closed is True


def test_fetch_observation_rejects_oversized_response(monkeypatch: pytest.MonkeyPatch) -> None:
    response = _Response(b"x" * (check_public_release_boundaries.MAX_RESPONSE_BYTES + 1))
    monkeypatch.setattr(
        check_public_release_boundaries, "urlopen", lambda *_args, **_kwargs: response
    )

    with pytest.raises(ValueError, match="1 MiB"):
        fetch_observation(response.geturl())

    assert response.closed is True


def test_fetch_observation_rejects_cleartext_url() -> None:
    with pytest.raises(ValueError, match="require HTTPS"):
        fetch_observation("http://api.getlorevia.com/health")


def test_public_boundary_main_reports_success_without_response_bodies(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        check_public_release_boundaries,
        "collect_public_boundaries",
        lambda *_args, **_kwargs: _passing_observations(),
    )

    assert check_public_release_boundaries.main([]) == 0
    output = capsys.readouterr().out
    assert RELEASE_SHA in output
    assert "release_sha" not in output


def test_public_boundary_main_fails_closed_without_printing_exception_details(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail(*_args: Any, **_kwargs: Any) -> dict[str, HttpObservation]:
        raise RuntimeError("response contained private data")

    monkeypatch.setattr(check_public_release_boundaries, "collect_public_boundaries", fail)

    assert check_public_release_boundaries.main([]) == 1
    error = capsys.readouterr().err
    assert "RuntimeError" in error
    assert "private data" not in error
