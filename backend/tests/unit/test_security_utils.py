from app.utils.security_utils import (
    API_CONTENT_SECURITY_POLICY,
    HSTS_POLICY,
    PERMISSIONS_POLICY,
    api_content_security_policy,
    apply_security_headers,
    permissions_policy,
)


def test_permissions_policy_disables_sensitive_browser_features():
    policy = permissions_policy()

    assert policy == PERMISSIONS_POLICY
    assert "camera=()" in policy
    assert "microphone=()" in policy
    assert "payment=()" in policy
    assert "usb=()" in policy


def test_api_content_security_policy_is_locked_down_for_api_responses():
    assert api_content_security_policy() == API_CONTENT_SECURITY_POLICY
    assert "default-src 'none'" in API_CONTENT_SECURITY_POLICY
    assert "frame-ancestors 'none'" in API_CONTENT_SECURITY_POLICY
    assert "form-action 'none'" in API_CONTENT_SECURITY_POLICY


def test_apply_security_headers_adds_hardened_headers():
    headers = {b"content-type": b"application/json"}

    updated_headers = apply_security_headers(
        headers,
        request_id="req-123",
        include_hsts=True,
    )

    assert updated_headers[b"x-request-id"] == b"req-123"
    assert updated_headers[b"x-frame-options"] == b"DENY"
    assert updated_headers[b"x-content-type-options"] == b"nosniff"
    assert updated_headers[b"referrer-policy"] == b"strict-origin-when-cross-origin"
    assert updated_headers[b"permissions-policy"] == PERMISSIONS_POLICY.encode()
    assert updated_headers[b"content-security-policy"] == API_CONTENT_SECURITY_POLICY.encode()
    assert updated_headers[b"strict-transport-security"] == HSTS_POLICY.encode()


def test_apply_security_headers_omits_hsts_when_disabled():
    headers = {b"strict-transport-security": b"old-value"}

    updated_headers = apply_security_headers(
        headers,
        request_id="req-456",
        include_hsts=False,
    )

    assert b"strict-transport-security" not in updated_headers
