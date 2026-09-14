import jwt

from app.core.security import (
    create_access_token,
    create_asset_token,
    create_refresh_token,
    decode_token,
)


def test_create_access_token_sets_type_and_version_claims():
    token = create_access_token("user-123", version=7)

    payload = decode_token(token)

    assert payload is not None
    assert payload["sub"] == "user-123"
    assert payload["type"] == "access"
    assert payload["ver"] == 7


def test_create_refresh_token_preserves_or_generates_session_ids():
    explicit_token = create_refresh_token("user-123", version=2, session_id="session-abc")
    generated_token = create_refresh_token("user-123")

    explicit_payload = decode_token(explicit_token)
    generated_payload = decode_token(generated_token)

    assert explicit_payload is not None
    assert explicit_payload["type"] == "refresh"
    assert explicit_payload["sid"] == "session-abc"
    assert explicit_payload["ver"] == 2

    assert generated_payload is not None
    assert generated_payload["type"] == "refresh"
    assert isinstance(generated_payload["sid"], str)
    assert generated_payload["sid"]


def test_create_asset_token_sets_resource_and_rejects_tampered_payloads():
    token = create_asset_token("user-123", resource="books/book-9/cover", expires_minutes=15)
    payload = decode_token(token)

    assert payload is not None
    assert payload["type"] == "asset"
    assert payload["res"] == "books/book-9/cover"

    raw_payload = jwt.decode(token, options={"verify_signature": False})
    tampered = jwt.encode(
        {**raw_payload, "res": "books/book-10/cover"},
        "wrong-test-secret-with-at-least-32-characters",
        algorithm="HS256",
    )

    assert decode_token(tampered) is None
