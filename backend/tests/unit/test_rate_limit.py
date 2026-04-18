from starlette.requests import Request

from app.api.deps.rate_limit import _client_identifier


def _request_with_headers(headers: dict[str, str], client_host: str = "127.0.0.1") -> Request:
    scope_headers = [(key.lower().encode("latin-1"), value.encode("latin-1")) for key, value in headers.items()]
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": scope_headers,
        "client": (client_host, 50000),
    }
    return Request(scope)


def test_client_identifier_prefers_cloudflare_header() -> None:
    request = _request_with_headers(
        {
            "x-forwarded-for": "198.51.100.7",
            "cf-connecting-ip": "203.0.113.11",
        }
    )

    assert _client_identifier(request) == "203.0.113.11"


def test_client_identifier_falls_back_to_socket_client() -> None:
    request = _request_with_headers({}, client_host="10.0.0.9")

    assert _client_identifier(request) == "10.0.0.9"
