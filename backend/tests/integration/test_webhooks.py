import hashlib
import hmac
import json
from contextlib import asynccontextmanager
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.config import allowed_hosts
from app.main import app
from app.models.user import PaddleWebhookEvent, Subscription, SubscriptionEvent, User


def _sign_payload(payload: dict, timestamp: int, secret: str) -> tuple[bytes, str]:
    raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    digest = hmac.new(
        secret.encode("utf-8"),
        f"{timestamp}:{raw_body.decode('utf-8')}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return raw_body, f"ts={timestamp};h1={digest}"


def _trusted_base_url() -> str:
    hosts = allowed_hosts()
    for preferred in ("localhost", "127.0.0.1"):
        if preferred in hosts:
            return f"http://{preferred}"
    if hosts:
        return f"https://{hosts[0]}"
    return "http://localhost"


def _patch_service_session(monkeypatch, db) -> None:
    @asynccontextmanager
    async def _db_session_factory():
        yield db

    monkeypatch.setattr("app.services.paddle_webhook_service.AsyncSessionLocal", _db_session_factory)


async def _create_user(db) -> User:
    user = User(
        email=f"webhook-{uuid.uuid4().hex[:8]}@lorevia.app",
        username=f"webhook-{uuid.uuid4().hex[:8]}",
        password_hash="hashed",
        email_verified_at=None,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


def _event_payload(
    *,
    event_id: str,
    event_type: str,
    user_id: uuid.UUID | None = None,
    plan: str = "author_annual",
    price_id: str = "pri_author_annual",
    customer_id: str = "ctm_123",
    subscription_id: str = "sub_123",
    transaction_id: str = "txn_123",
    status: str = "active",
) -> dict:
    custom_data = {"plan": plan}
    if user_id is not None:
        custom_data["user_id"] = str(user_id)

    data = {
        "customer_id": customer_id,
        "status": status,
        "custom_data": custom_data,
        "items": [
            {
                "price": {
                    "id": price_id,
                    "name": "Author annual",
                    "billing_cycle": {"interval": "year"},
                }
            }
        ],
    }

    if event_type.startswith("transaction."):
        data["id"] = transaction_id
        data["subscription_id"] = subscription_id
    else:
        data["id"] = subscription_id
        data["transaction_id"] = transaction_id

    return {
        "event_id": event_id,
        "event_type": event_type,
        "notification_id": f"ntf_{event_id}",
        "data": data,
    }


@pytest.mark.asyncio
async def test_paddle_webhook_rejects_invalid_signature(monkeypatch):
    secret = "pdl_secret_test"
    payload = {"event_id": "evt_123", "event_type": "subscription.updated", "data": {}}

    monkeypatch.setattr("app.services.paddle_service.settings.PADDLE_WEBHOOK_SECRET", secret, raising=False)
    monkeypatch.setattr("app.services.paddle_service.settings.PADDLE_WEBHOOK_TOLERANCE_SECONDS", 300, raising=False)
    monkeypatch.setattr("app.services.paddle_service.time.time", lambda: 1_700_000_060)

    async with AsyncClient(transport=ASGITransport(app=app), base_url=_trusted_base_url()) as client:
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

    async with AsyncClient(transport=ASGITransport(app=app), base_url=_trusted_base_url()) as client:
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

    async def _fake_process_paddle_webhook(event: dict):
        assert event["event_id"] == "evt_123"
        return {"received": True}

    monkeypatch.setattr("app.services.paddle_service.settings.PADDLE_WEBHOOK_SECRET", secret, raising=False)
    monkeypatch.setattr("app.services.paddle_service.settings.PADDLE_WEBHOOK_TOLERANCE_SECONDS", 300, raising=False)
    monkeypatch.setattr("app.services.paddle_service.time.time", lambda: timestamp + 60)
    monkeypatch.setattr("app.api.v1.routes.webhooks.process_paddle_webhook", _fake_process_paddle_webhook)

    async with AsyncClient(transport=ASGITransport(app=app), base_url=_trusted_base_url()) as client:
        response = await client.post(
            "/api/v1/webhooks/paddle",
            content=raw_body,
            headers={"Paddle-Signature": signature, "Content-Type": "application/json"},
        )

    assert response.status_code == 200
    assert response.json() == {"received": True}


@pytest.mark.asyncio
async def test_paddle_webhook_deduplicates_processed_events_and_sends_confirmation_once(client, db, monkeypatch):
    secret = "pdl_secret_test"
    timestamp = 1_700_000_000
    user = await _create_user(db)
    sent_emails: list[tuple[str, str]] = []

    async def _fake_send_subscription_confirmation(email: str, plan: str) -> None:
        sent_emails.append((email, plan))

    _patch_service_session(monkeypatch, db)
    monkeypatch.setattr("app.services.paddle_service.settings.PADDLE_WEBHOOK_SECRET", secret, raising=False)
    monkeypatch.setattr("app.services.paddle_service.settings.PADDLE_WEBHOOK_TOLERANCE_SECONDS", 300, raising=False)
    monkeypatch.setattr("app.services.paddle_service.time.time", lambda: timestamp + 60)
    monkeypatch.setattr(
        "app.services.paddle_webhook_service.send_subscription_confirmation",
        _fake_send_subscription_confirmation,
    )

    payload = _event_payload(
        event_id="evt_txn_complete",
        event_type="transaction.completed",
        user_id=user.id,
        status="completed",
    )
    raw_body, signature = _sign_payload(payload, timestamp, secret)

    first_response = await client.post(
        "/api/v1/webhooks/paddle",
        content=raw_body,
        headers={"Paddle-Signature": signature, "Content-Type": "application/json"},
    )
    second_response = await client.post(
        "/api/v1/webhooks/paddle",
        content=raw_body,
        headers={"Paddle-Signature": signature, "Content-Type": "application/json"},
    )

    assert first_response.status_code == 200
    assert first_response.json() == {"received": True}
    assert second_response.status_code == 200
    assert second_response.json() == {"received": True, "duplicate": True}

    await db.refresh(user)
    assert user.tier == "author"

    subscription = (
        await db.execute(
            select(Subscription).where(Subscription.user_id == user.id)
        )
    ).scalars().one()
    assert subscription.plan == "author_annual"
    assert subscription.status == "active"
    assert subscription.paddle_transaction_id == "txn_123"

    subscription_events = (
        await db.execute(
            select(SubscriptionEvent).where(SubscriptionEvent.user_id == user.id)
        )
    ).scalars().all()
    assert [event.event_type for event in subscription_events] == ["subscription_activated"]

    webhook_event = (
        await db.execute(
            select(PaddleWebhookEvent).where(PaddleWebhookEvent.event_id == "evt_txn_complete")
        )
    ).scalars().one()
    assert webhook_event.processing_status == "processed"
    assert webhook_event.duplicate_count == 1
    assert sent_emails == [(user.email, "author")]


@pytest.mark.asyncio
async def test_paddle_webhook_failed_event_can_retry_successfully(client, db, monkeypatch):
    secret = "pdl_secret_test"
    timestamp = 1_700_000_000
    user = await _create_user(db)
    call_count = {"count": 0}
    original_record_subscription_event = __import__(
        "app.services.paddle_webhook_service",
        fromlist=["record_subscription_event"],
    ).record_subscription_event

    async def _flaky_record_subscription_event(*args, **kwargs):
        call_count["count"] += 1
        if call_count["count"] == 1:
            raise RuntimeError("transient billing write failure")
        return await original_record_subscription_event(*args, **kwargs)

    _patch_service_session(monkeypatch, db)
    monkeypatch.setattr("app.services.paddle_service.settings.PADDLE_WEBHOOK_SECRET", secret, raising=False)
    monkeypatch.setattr("app.services.paddle_service.settings.PADDLE_WEBHOOK_TOLERANCE_SECONDS", 300, raising=False)
    monkeypatch.setattr("app.services.paddle_service.time.time", lambda: timestamp + 60)
    monkeypatch.setattr(
        "app.services.paddle_webhook_service.record_subscription_event",
        _flaky_record_subscription_event,
    )

    payload = _event_payload(
        event_id="evt_retry_activate",
        event_type="subscription.activated",
        user_id=user.id,
        status="active",
    )
    raw_body, signature = _sign_payload(payload, timestamp, secret)

    with pytest.raises(RuntimeError, match="transient billing write failure"):
        await client.post(
            "/api/v1/webhooks/paddle",
            content=raw_body,
            headers={"Paddle-Signature": signature, "Content-Type": "application/json"},
        )

    webhook_event = (
        await db.execute(
            select(PaddleWebhookEvent).where(PaddleWebhookEvent.event_id == "evt_retry_activate")
        )
    ).scalars().one()
    assert webhook_event.processing_status == "failed"
    assert "transient billing write failure" in (webhook_event.last_error or "")

    response = await client.post(
        "/api/v1/webhooks/paddle",
        content=raw_body,
        headers={"Paddle-Signature": signature, "Content-Type": "application/json"},
    )

    assert response.status_code == 200
    assert response.json() == {"received": True}

    await db.refresh(user)
    assert user.tier == "author"

    webhook_event = (
        await db.execute(
            select(PaddleWebhookEvent).where(PaddleWebhookEvent.event_id == "evt_retry_activate")
        )
    ).scalars().one()
    assert webhook_event.processing_status == "processed"
    assert webhook_event.duplicate_count == 1

    subscription_events = (
        await db.execute(
            select(SubscriptionEvent).where(SubscriptionEvent.user_id == user.id)
        )
    ).scalars().all()
    assert [event.event_type for event in subscription_events] == ["subscription_activated"]


@pytest.mark.asyncio
async def test_paddle_webhook_subscription_lifecycle_and_transaction_sync(client, db, monkeypatch):
    secret = "pdl_secret_test"
    timestamp = 1_700_000_000
    user = await _create_user(db)

    _patch_service_session(monkeypatch, db)
    monkeypatch.setattr("app.services.paddle_service.settings.PADDLE_WEBHOOK_SECRET", secret, raising=False)
    monkeypatch.setattr("app.services.paddle_service.settings.PADDLE_WEBHOOK_TOLERANCE_SECONDS", 300, raising=False)
    monkeypatch.setattr("app.services.paddle_service.time.time", lambda: timestamp + 60)

    cases = [
        ("subscription.created", "evt_created", "pending", "free"),
        ("subscription.trialing", "evt_trialing", "trialing", "author"),
        ("subscription.updated", "evt_updated", "active", "author"),
        ("transaction.updated", "evt_txn_updated", "billed", "author"),
        ("transaction.payment_failed", "evt_txn_failed", "payment_failed", "author"),
        ("transaction.past_due", "evt_txn_past_due", "past_due", "author"),
        ("subscription.past_due", "evt_sub_past_due", "past_due", "author"),
        ("subscription.paused", "evt_paused", "paused", "free"),
        ("subscription.resumed", "evt_resumed", "active", "author"),
        ("subscription.canceled", "evt_cancel_scheduled", "active", "author"),
        ("subscription.canceled", "evt_cancel_final", "canceled", "free"),
    ]

    for index, (event_type, event_id, status, expected_tier) in enumerate(cases):
        payload = _event_payload(
            event_id=event_id,
            event_type=event_type,
            user_id=user.id,
            status=status,
        )
        raw_body, signature = _sign_payload(payload, timestamp + index, secret)
        monkeypatch.setattr("app.services.paddle_service.time.time", lambda value=timestamp + index + 60: value)
        response = await client.post(
            "/api/v1/webhooks/paddle",
            content=raw_body,
            headers={"Paddle-Signature": signature, "Content-Type": "application/json"},
        )
        assert response.status_code == 200

        await db.refresh(user)
        assert user.tier == expected_tier

    subscription = (
        await db.execute(
            select(Subscription).where(Subscription.user_id == user.id)
        )
    ).scalars().one()
    assert subscription.paddle_customer_id == "ctm_123"
    assert subscription.paddle_sub_id == "sub_123"
    assert subscription.paddle_transaction_id == "txn_123"
    assert subscription.status == "canceled"

    subscription_events = (
        await db.execute(
            select(SubscriptionEvent)
            .where(SubscriptionEvent.user_id == user.id)
            .order_by(SubscriptionEvent.occurred_at.asc())
        )
    ).scalars().all()
    assert [event.event_type for event in subscription_events] == [
        "subscription_activated",
        "subscription_past_due",
        "subscription_paused",
        "subscription_activated",
        "subscription_canceled",
    ]


@pytest.mark.asyncio
async def test_paddle_webhook_ignores_unknown_events_but_records_them(client, db, monkeypatch):
    secret = "pdl_secret_test"
    timestamp = 1_700_000_000

    _patch_service_session(monkeypatch, db)
    monkeypatch.setattr("app.services.paddle_service.settings.PADDLE_WEBHOOK_SECRET", secret, raising=False)
    monkeypatch.setattr("app.services.paddle_service.settings.PADDLE_WEBHOOK_TOLERANCE_SECONDS", 300, raising=False)
    monkeypatch.setattr("app.services.paddle_service.time.time", lambda: timestamp + 60)

    payload = {"event_id": "evt_unknown", "event_type": "subscription.foo", "data": {"id": "sub_123"}}
    raw_body, signature = _sign_payload(payload, timestamp, secret)

    response = await client.post(
        "/api/v1/webhooks/paddle",
        content=raw_body,
        headers={"Paddle-Signature": signature, "Content-Type": "application/json"},
    )

    assert response.status_code == 200
    assert response.json() == {"received": True, "ignored": True}

    webhook_event = (
        await db.execute(
            select(PaddleWebhookEvent).where(PaddleWebhookEvent.event_id == "evt_unknown")
        )
    ).scalars().one()
    assert webhook_event.processing_status == "ignored"


@pytest.mark.asyncio
async def test_paddle_webhook_fails_when_supported_event_cannot_be_linked_to_local_user(client, db, monkeypatch):
    secret = "pdl_secret_test"
    timestamp = 1_700_000_000

    _patch_service_session(monkeypatch, db)
    monkeypatch.setattr("app.services.paddle_service.settings.PADDLE_WEBHOOK_SECRET", secret, raising=False)
    monkeypatch.setattr("app.services.paddle_service.settings.PADDLE_WEBHOOK_TOLERANCE_SECONDS", 300, raising=False)
    monkeypatch.setattr("app.services.paddle_service.time.time", lambda: timestamp + 60)

    payload = _event_payload(
        event_id="evt_unlinked_paid_event",
        event_type="subscription.activated",
        user_id=None,
        status="active",
    )
    payload["data"]["custom_data"] = {}
    raw_body, signature = _sign_payload(payload, timestamp, secret)

    with pytest.raises(RuntimeError, match="Unable to associate Paddle webhook"):
        await client.post(
            "/api/v1/webhooks/paddle",
            content=raw_body,
            headers={"Paddle-Signature": signature, "Content-Type": "application/json"},
        )

    webhook_event = (
        await db.execute(
            select(PaddleWebhookEvent).where(PaddleWebhookEvent.event_id == "evt_unlinked_paid_event")
        )
    ).scalars().one()
    assert webhook_event.processing_status == "failed"


@pytest.mark.asyncio
async def test_transaction_completed_does_not_overwrite_existing_paused_status(client, db, monkeypatch):
    secret = "pdl_secret_test"
    timestamp = 1_700_000_000
    user = await _create_user(db)
    subscription = Subscription(
        user_id=user.id,
        plan="author_annual",
        status="paused",
        paddle_customer_id="ctm_123",
        paddle_sub_id="sub_123",
    )
    db.add(subscription)
    await db.commit()

    _patch_service_session(monkeypatch, db)
    monkeypatch.setattr("app.services.paddle_service.settings.PADDLE_WEBHOOK_SECRET", secret, raising=False)
    monkeypatch.setattr("app.services.paddle_service.settings.PADDLE_WEBHOOK_TOLERANCE_SECONDS", 300, raising=False)
    monkeypatch.setattr("app.services.paddle_service.time.time", lambda: timestamp + 60)

    payload = _event_payload(
        event_id="evt_txn_completed_preserve_paused",
        event_type="transaction.completed",
        user_id=user.id,
        status="completed",
    )
    raw_body, signature = _sign_payload(payload, timestamp, secret)

    response = await client.post(
        "/api/v1/webhooks/paddle",
        content=raw_body,
        headers={"Paddle-Signature": signature, "Content-Type": "application/json"},
    )

    assert response.status_code == 200
    await db.refresh(user)
    assert user.tier == "free"

    refreshed_subscription = (
        await db.execute(
            select(Subscription).where(Subscription.user_id == user.id)
        )
    ).scalars().one()
    assert refreshed_subscription.status == "paused"
