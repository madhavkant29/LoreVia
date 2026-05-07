import hashlib
import hmac
import json

from app.services import paddle_service


def _sign_payload(payload: dict, timestamp: int, secret: str) -> tuple[bytes, str]:
    raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    digest = hmac.new(
        secret.encode("utf-8"),
        f"{timestamp}:{raw_body.decode('utf-8')}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return raw_body, f"ts={timestamp};h1={digest}"


def test_verify_webhook_signature_accepts_valid_recent_signature(monkeypatch):
    secret = "pdl_secret_test"
    timestamp = 1_700_000_000
    payload = {"event_id": "evt_123", "event_type": "subscription.updated", "data": {}}
    raw_body, signature = _sign_payload(payload, timestamp, secret)

    monkeypatch.setattr("app.services.paddle_service.settings.PADDLE_WEBHOOK_SECRET", secret, raising=False)
    monkeypatch.setattr("app.services.paddle_service.settings.PADDLE_WEBHOOK_TOLERANCE_SECONDS", 300, raising=False)
    monkeypatch.setattr("app.services.paddle_service.time.time", lambda: timestamp + 60)

    assert paddle_service.verify_webhook_signature(raw_body, signature) is True


def test_verify_webhook_signature_rejects_stale_timestamp(monkeypatch):
    secret = "pdl_secret_test"
    timestamp = 1_700_000_000
    payload = {"event_id": "evt_123", "event_type": "subscription.updated", "data": {}}
    raw_body, signature = _sign_payload(payload, timestamp, secret)

    monkeypatch.setattr("app.services.paddle_service.settings.PADDLE_WEBHOOK_SECRET", secret, raising=False)
    monkeypatch.setattr("app.services.paddle_service.settings.PADDLE_WEBHOOK_TOLERANCE_SECONDS", 300, raising=False)
    monkeypatch.setattr("app.services.paddle_service.time.time", lambda: timestamp + 301)

    assert paddle_service.verify_webhook_signature(raw_body, signature) is False


def test_verify_webhook_signature_rejects_invalid_timestamp(monkeypatch):
    secret = "pdl_secret_test"

    monkeypatch.setattr("app.services.paddle_service.settings.PADDLE_WEBHOOK_SECRET", secret, raising=False)
    monkeypatch.setattr("app.services.paddle_service.settings.PADDLE_WEBHOOK_TOLERANCE_SECONDS", 300, raising=False)

    assert paddle_service.verify_webhook_signature(b"{}", "ts=not-a-number;h1=abc123") is False


def test_verify_webhook_signature_rejects_mismatched_signature(monkeypatch):
    secret = "pdl_secret_test"
    timestamp = 1_700_000_000
    payload = {"event_id": "evt_123", "event_type": "subscription.updated", "data": {}}
    raw_body, _signature = _sign_payload(payload, timestamp, secret)

    monkeypatch.setattr("app.services.paddle_service.settings.PADDLE_WEBHOOK_SECRET", secret, raising=False)
    monkeypatch.setattr("app.services.paddle_service.settings.PADDLE_WEBHOOK_TOLERANCE_SECONDS", 300, raising=False)
    monkeypatch.setattr("app.services.paddle_service.time.time", lambda: timestamp)

    assert paddle_service.verify_webhook_signature(raw_body, "ts=1700000000;h1=deadbeef") is False
