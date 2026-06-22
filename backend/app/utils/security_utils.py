API_CONTENT_SECURITY_POLICY = (
    "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
)
HSTS_POLICY = "max-age=31536000; includeSubDomains; preload"
PERMISSIONS_POLICY = (
    "accelerometer=(), camera=(), display-capture=(), geolocation=(), "
    "gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()"
)


def api_content_security_policy() -> str:
    return API_CONTENT_SECURITY_POLICY


def permissions_policy() -> str:
    return PERMISSIONS_POLICY


def apply_security_headers(
    headers: dict[bytes, bytes],
    *,
    request_id: str,
    include_hsts: bool,
) -> dict[bytes, bytes]:
    headers[b"x-request-id"] = request_id.encode()
    headers[b"x-frame-options"] = b"DENY"
    headers[b"x-content-type-options"] = b"nosniff"
    headers[b"referrer-policy"] = b"strict-origin-when-cross-origin"
    headers[b"permissions-policy"] = permissions_policy().encode()
    headers[b"content-security-policy"] = api_content_security_policy().encode()
    if include_hsts:
        headers[b"strict-transport-security"] = HSTS_POLICY.encode()
    else:
        headers.pop(b"strict-transport-security", None)
    return headers
