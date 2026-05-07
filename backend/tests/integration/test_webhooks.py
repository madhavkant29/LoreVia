import hashlib
import hmac
import json
from contextlib import asynccontextmanager
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.main import app
from app.models.user import Subscription, User


def _sign_payload(payload: dict, timestamp: int, secret: str) -> tuple[bytes, str]:
    raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    digest = hmac.new(
        secret.encode("utf-8"),
        f"{timestamp}:{raw_body.decode('utf-8')}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return raw_body, f"ts={timestamp};h1={digest}"


@pytest.mark.asyncio
async def test_paddle_webhook_rejects_invalid_signature(monkeypatch):
    secret = "pdl_secret_test"
    payload = {"event_id": "evt_123", "event_type": "subscription.updated", "data": {}}

    monkeypatch.setattr("app.services.paddle_service.settings.PADDLE_WEBHOOK_SECRET", secret, raising=False)
    monkeypatch.setattr("app.services.paddle_service.settings.PADDLE_WEBHOOK_TOLERANCE_SECONDS", 300, raising=False)
    monkeypatch.setattr("app.services.paddle_service.time.time", lambda: 1_700_000_060)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as client:
        response = await client.post(
            "/api/v1/webhooks/paddle",
            content=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            headers={"Paddle-Signature": "ts=1700000000;h1=deadbeef", "Content-Type": "application/json"},
        )

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid request."}


@pytest.mark.asyncio
async def test_paddle_webhook_rejects_stale_signature(monkeypatch):
    secret = "pdl_secret_test"
    timestamp = 1_700_000_000
    payload = {"event_id": "evt_123", "event_type": "subscription.updated", "data": {}}
    raw_body, signature = _sign_payload(payload, timestamp, secret)

    monkeypatch.setattr("app.services.paddle_service.settings.PADDLE_WEBHOOK_SECRET", secret, raising=False)
    monkeypatch.setattr("app.services.paddle_service.settings.PADDLE_WEBHOOK_TOLERANCE_SECONDS", 300, raising=False)
    monkeypatch.setattr("app.services.paddle_service.time.time", lambda: timestamp + 301)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as client:
        response = await client.post(
            "/api/v1/webhooks/paddle",
            content=raw_body,
            headers={"Paddle-Signature": signature, "Content-Type": "application/json"},
        )

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid request."}


@pytest.mark.asyncio
async def test_paddle_webhook_accepts_valid_recent_signature(monkeypatch):
    secret = "pdl_secret_test"
    timestamp = 1_700_000_000
    payload = {"event_id": "evt_123", "event_type": "subscription.updated", "data": {}}
    raw_body, signature = _sign_payload(payload, timestamp, secret)

    @asynccontextmanager
    async def _fake_session_factory():
        class _FakeSession:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

        yield _FakeSession()

    monkeypatch.setattr("app.services.paddle_service.settings.PADDLE_WEBHOOK_SECRET", secret, raising=False)
    monkeypatch.setattr("app.services.paddle_service.settings.PADDLE_WEBHOOK_TOLERANCE_SECONDS", 300, raising=False)
    monkeypatch.setattr("app.services.paddle_service.time.time", lambda: timestamp + 60)
    monkeypatch.setattr("app.api.v1.routes.webhooks.AsyncSessionLocal", _fake_session_factory)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as client:
        response = await client.post(
            "/api/v1/webhooks/paddle",
            content=raw_body,
            headers={"Paddle-Signature": signature, "Content-Type": "application/json"},
        )

    assert response.status_code == 200
    assert response.json() == {"received": True}


@pytest.mark.asyncio
async def test_paddle_webhook_upserts_subscription_and_downgrades_on_pause(client, db, monkeypatch):
    from app.core.security import create_access_token

    secret = "pdl_secret_test"
    timestamp = 1_700_000_000

    user = User(
        email=f"webhook-{uuid.uuid4().hex[:8]}@lorevia.app",
        username=f"webhook-{uuid.uuid4().hex[:8]}",
        password_hash="hashed",
        email_verified_at=None,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    assert create_access_token(str(user.id))

    @asynccontextmanager
    async def _db_session_factory():
        yield db

    monkeypatch.setattr("app.services.paddle_service.settings.PADDLE_WEBHOOK_SECRET", secret, raising=False)
    monkeypatch.setattr("app.services.paddle_service.settings.PADDLE_WEBHOOK_TOLERANCE_SECONDS", 300, raising=False)
    monkeypatch.setattr("app.services.paddle_service.time.time", lambda: timestamp + 60)
    monkeypatch.setattr("app.api.v1.routes.webhooks.AsyncSessionLocal", _db_session_factory)

    activate_payload = {
        "event_id": "evt_activate_123",
        "event_type": "transaction.completed",
        "data": {
            "id": "txn_123",
            "customer_id": "ctm_123",
            "subscription_id": "sub_123",
            "status": "completed",
            "custom_data": {
                "user_id": str(user.id),
                "plan": "reader_annual",
            },
            "items": [
                {
                    "price": {
                        "id": "pri_reader_annual",
                        "name": "Reader annual",
                        "billing_cycle": {"interval": "year"},
                    }
                }
            ],
        },
    }
    activate_raw, activate_signature = _sign_payload(activate_payload, timestamp, secret)

    activate_response = await client.post(
        "/api/v1/webhooks/paddle",
        content=activate_raw,
        headers={"Paddle-Signature": activate_signature, "Content-Type": "application/json"},
    )

    assert activate_response.status_code == 200
    await db.refresh(user)
    assert user.tier == "reader"
    subscription = (
        await db.execute(
            select(Subscription).where(Subscription.user_id == user.id)
        )
    ).scalars().first()
    assert subscription is not None
    assert subscription.plan == "reader_annual"
    assert subscription.paddle_sub_id == "sub_123"

    pause_payload = {
        "event_id": "evt_pause_123",
        "event_type": "subscription.paused",
        "data": {
            "id": "sub_123",
            "customer_id": "ctm_123",
            "status": "paused",
        },
    }
    pause_raw, pause_signature = _sign_payload(pause_payload, timestamp + 1, secret)
    monkeypatch.setattr("app.services.paddle_service.time.time", lambda: timestamp + 61)

    pause_response = await client.post(
        "/api/v1/webhooks/paddle",
        content=pause_raw,
        headers={"Paddle-Signature": pause_signature, "Content-Type": "application/json"},
    )

    assert pause_response.status_code == 200
    await db.refresh(user)
    assert user.tier == "free"
