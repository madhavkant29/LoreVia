import hashlib
import hmac
import json
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.config import allowed_hosts
from app.main import app
from app.models.user import (
    PaddleWebhookEvent,
    RefundReview,
    Subscription,
    SubscriptionEmailEvent,
    SubscriptionEvent,
    User,
)
from app.utils.billing_utils import (
    SUBSCRIPTION_EMAIL_PAYMENT_FAILED,
    SUBSCRIPTION_EMAIL_RENEWAL_SUCCEEDED,
)
from app.utils.webhook_request_utils import PADDLE_WEBHOOK_MAX_BODY_BYTES


def _sign_payload(payload: dict, timestamp: int, secret: str) -> tuple[bytes, str]:
    raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    digest = hmac.new(
        secret.encode("utf-8"),
        f"{timestamp}:{raw_body.decode('utf-8')}".encode(),
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

    monkeypatch.setattr(
        "app.services.paddle_webhook_service.AsyncSessionLocal", _db_session_factory
    )


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
    occurred_at: str | None = None,
    billing_period: tuple[str, str] | None = None,
    scheduled_change: dict | None = None,
    total_minor: str | None = None,
    currency_code: str = "USD",
    origin: str | None = None,
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

    if billing_period is not None:
        starts_at, ends_at = billing_period
        data["current_billing_period"] = {"starts_at": starts_at, "ends_at": ends_at}

    if scheduled_change is not None:
        data["scheduled_change"] = scheduled_change

    if total_minor is not None:
        data["details"] = {"totals": {"total": total_minor}}
        data["currency_code"] = currency_code

    if origin is not None:
        data["origin"] = origin

    if event_type.startswith("transaction."):
        data["id"] = transaction_id
        data["subscription_id"] = subscription_id
    else:
        data["id"] = subscription_id
        data["transaction_id"] = transaction_id

    payload = {
        "event_id": event_id,
        "event_type": event_type,
        "notification_id": f"ntf_{event_id}",
        "data": data,
    }
    if occurred_at is not None:
        payload["occurred_at"] = occurred_at
    return payload


def _adjustment_payload(
    *,
    event_id: str,
    transaction_id: str,
    adjustment_id: str,
    status: str,
    action: str = "refund",
) -> dict:
    return {
        "event_id": event_id,
        "event_type": "adjustment.updated",
        "notification_id": f"ntf_{event_id}",
        "data": {
            "id": adjustment_id,
            "action": action,
            "status": status,
            "transaction_id": transaction_id,
        },
    }


@pytest.mark.asyncio
async def test_paddle_webhook_rejects_invalid_signature(monkeypatch):
    secret = "pdl_secret_test"
    payload = {"event_id": "evt_123", "event_type": "subscription.updated", "data": {}}

    monkeypatch.setattr(
        "app.services.paddle_service.settings.PADDLE_WEBHOOK_SECRET", secret, raising=False
    )
    monkeypatch.setattr(
        "app.services.paddle_service.settings.PADDLE_WEBHOOK_TOLERANCE_SECONDS", 300, raising=False
    )
    monkeypatch.setattr("app.services.paddle_service.time.time", lambda: 1_700_000_060)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url=_trusted_base_url()
    ) as client:
        response = await client.post(
            "/api/v1/webhooks/paddle",
            content=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            headers={
                "Paddle-Signature": "ts=1700000000;h1=deadbeef",
                "Content-Type": "application/json",
            },
        )

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid request."}


@pytest.mark.asyncio
async def test_paddle_webhook_rejects_payload_larger_than_one_mib(monkeypatch):
    monkeypatch.setattr("app.api.v1.routes.webhooks.paddle_webhooks_configured", lambda: True)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url=_trusted_base_url()
    ) as client:
        response = await client.post(
            "/api/v1/webhooks/paddle",
            content=b"x" * (PADDLE_WEBHOOK_MAX_BODY_BYTES + 1),
            headers={
                "Paddle-Signature": "ts=1700000000;h1=unused",
                "Content-Type": "application/json",
            },
        )

    assert response.status_code == 413
    assert response.json() == {"detail": "Paddle webhook payload exceeds 1 MiB."}


@pytest.mark.asyncio
async def test_paddle_webhook_verifies_and_parses_the_same_raw_body(monkeypatch):
    raw_body = (
        b' { "event_id" : "evt_exact_bytes", "event_type" : "subscription.updated", "data" : {} }\n'
    )
    captured: dict[str, object] = {}

    def fake_verify_webhook_signature(payload: bytes, signature: str | None) -> bool:
        captured["verified_payload"] = payload
        captured["signature"] = signature
        return True

    async def fake_process_paddle_webhook(event: dict):
        captured["event"] = event
        return {"received": True}

    monkeypatch.setattr("app.api.v1.routes.webhooks.paddle_webhooks_configured", lambda: True)
    monkeypatch.setattr(
        "app.api.v1.routes.webhooks.verify_webhook_signature",
        fake_verify_webhook_signature,
    )
    monkeypatch.setattr(
        "app.api.v1.routes.webhooks.process_paddle_webhook", fake_process_paddle_webhook
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url=_trusted_base_url()
    ) as client:
        response = await client.post(
            "/api/v1/webhooks/paddle",
            content=raw_body,
            headers={
                "Paddle-Signature": "ts=1700000000;h1=exact",
                "Content-Type": "application/json",
            },
        )

    assert response.status_code == 200
    assert captured["verified_payload"] == raw_body
    assert captured["event"] == {
        "event_id": "evt_exact_bytes",
        "event_type": "subscription.updated",
        "data": {},
    }


@pytest.mark.asyncio
async def test_paddle_webhook_rejects_stale_signature(monkeypatch):
    secret = "pdl_secret_test"
    timestamp = 1_700_000_000
    payload = {"event_id": "evt_123", "event_type": "subscription.updated", "data": {}}
    raw_body, signature = _sign_payload(payload, timestamp, secret)

    monkeypatch.setattr(
        "app.services.paddle_service.settings.PADDLE_WEBHOOK_SECRET", secret, raising=False
    )
    monkeypatch.setattr(
        "app.services.paddle_service.settings.PADDLE_WEBHOOK_TOLERANCE_SECONDS", 300, raising=False
    )
    monkeypatch.setattr("app.services.paddle_service.time.time", lambda: timestamp + 301)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url=_trusted_base_url()
    ) as client:
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

    monkeypatch.setattr(
        "app.services.paddle_service.settings.PADDLE_WEBHOOK_SECRET", secret, raising=False
    )
    monkeypatch.setattr(
        "app.services.paddle_service.settings.PADDLE_WEBHOOK_TOLERANCE_SECONDS", 300, raising=False
    )
    monkeypatch.setattr("app.services.paddle_service.time.time", lambda: timestamp + 60)
    monkeypatch.setattr(
        "app.api.v1.routes.webhooks.process_paddle_webhook", _fake_process_paddle_webhook
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url=_trusted_base_url()
    ) as client:
        response = await client.post(
            "/api/v1/webhooks/paddle",
            content=raw_body,
            headers={"Paddle-Signature": signature, "Content-Type": "application/json"},
        )

    assert response.status_code == 200
    assert response.json() == {"received": True}


@pytest.mark.asyncio
async def test_paddle_webhook_deduplicates_processed_events_and_sends_confirmation_once(
    client, db, monkeypatch
):
    secret = "pdl_secret_test"
    timestamp = 1_700_000_000
    user = await _create_user(db)
    sent_emails: list[tuple[str, str]] = []

    async def _fake_send_subscription_confirmation(email: str, plan: str) -> None:
        sent_emails.append((email, plan))

    _patch_service_session(monkeypatch, db)
    monkeypatch.setattr(
        "app.services.paddle_service.settings.PADDLE_WEBHOOK_SECRET", secret, raising=False
    )
    monkeypatch.setattr(
        "app.services.paddle_service.settings.PADDLE_WEBHOOK_TOLERANCE_SECONDS", 300, raising=False
    )
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
        (await db.execute(select(Subscription).where(Subscription.user_id == user.id)))
        .scalars()
        .one()
    )
    assert subscription.plan == "author_annual"
    assert subscription.status == "active"
    assert subscription.paddle_transaction_id == "txn_123"

    subscription_events = (
        (await db.execute(select(SubscriptionEvent).where(SubscriptionEvent.user_id == user.id)))
        .scalars()
        .all()
    )
    assert [
        event.event_type
        for event in subscription_events
        if event.event_type != "paddle_state_applied"
    ] == ["subscription_activated"]
    assert sum(event.event_type == "paddle_state_applied" for event in subscription_events) == 1

    webhook_event = (
        (
            await db.execute(
                select(PaddleWebhookEvent).where(PaddleWebhookEvent.event_id == "evt_txn_complete")
            )
        )
        .scalars()
        .one()
    )
    assert webhook_event.processing_status == "processed"
    assert webhook_event.duplicate_count == 1
    assert sent_emails == [(user.email, "author")]


@pytest.mark.asyncio
async def test_paddle_webhook_sends_cancellation_email_only_for_final_cancellation(
    client, db, monkeypatch
):
    secret = "pdl_secret_test"
    timestamp = 1_700_000_000
    user = await _create_user(db)
    sent_emails: list[tuple[str, str]] = []

    async def _fake_send_subscription_cancellation(email: str, plan: str) -> None:
        sent_emails.append((email, plan))

    _patch_service_session(monkeypatch, db)
    monkeypatch.setattr(
        "app.services.paddle_service.settings.PADDLE_WEBHOOK_SECRET", secret, raising=False
    )
    monkeypatch.setattr(
        "app.services.paddle_service.settings.PADDLE_WEBHOOK_TOLERANCE_SECONDS", 300, raising=False
    )
    monkeypatch.setattr(
        "app.services.paddle_webhook_service.send_subscription_cancellation",
        _fake_send_subscription_cancellation,
    )

    activated_payload = _event_payload(
        event_id="evt_activate_for_cancel_email",
        event_type="subscription.activated",
        user_id=user.id,
        status="active",
    )
    activated_body, activated_signature = _sign_payload(activated_payload, timestamp, secret)
    monkeypatch.setattr("app.services.paddle_service.time.time", lambda: timestamp + 60)
    activated_response = await client.post(
        "/api/v1/webhooks/paddle",
        content=activated_body,
        headers={"Paddle-Signature": activated_signature, "Content-Type": "application/json"},
    )

    scheduled_payload = _event_payload(
        event_id="evt_cancel_scheduled_email",
        event_type="subscription.canceled",
        user_id=user.id,
        status="active",
    )
    scheduled_body, scheduled_signature = _sign_payload(scheduled_payload, timestamp + 1, secret)
    monkeypatch.setattr("app.services.paddle_service.time.time", lambda: timestamp + 61)
    scheduled_response = await client.post(
        "/api/v1/webhooks/paddle",
        content=scheduled_body,
        headers={"Paddle-Signature": scheduled_signature, "Content-Type": "application/json"},
    )

    final_payload = _event_payload(
        event_id="evt_cancel_final_email",
        event_type="subscription.canceled",
        user_id=user.id,
        status="canceled",
    )
    final_body, final_signature = _sign_payload(final_payload, timestamp + 2, secret)
    monkeypatch.setattr("app.services.paddle_service.time.time", lambda: timestamp + 62)
    final_response = await client.post(
        "/api/v1/webhooks/paddle",
        content=final_body,
        headers={"Paddle-Signature": final_signature, "Content-Type": "application/json"},
    )

    assert activated_response.status_code == 200
    assert scheduled_response.status_code == 200
    assert final_response.status_code == 200
    assert sent_emails == [(user.email, "author")]


@pytest.mark.parametrize(
    "processing_error",
    [
        pytest.param(RuntimeError("transient billing write failure"), id="expected-runtime"),
        pytest.param(KeyError("unexpected payload regression"), id="unexpected-key-error"),
    ],
)
@pytest.mark.asyncio
async def test_paddle_webhook_failed_event_can_retry_successfully(
    client, db, monkeypatch, processing_error
):
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
            raise processing_error
        return await original_record_subscription_event(*args, **kwargs)

    _patch_service_session(monkeypatch, db)
    monkeypatch.setattr(
        "app.services.paddle_service.settings.PADDLE_WEBHOOK_SECRET", secret, raising=False
    )
    monkeypatch.setattr(
        "app.services.paddle_service.settings.PADDLE_WEBHOOK_TOLERANCE_SECONDS", 300, raising=False
    )
    monkeypatch.setattr("app.services.paddle_service.time.time", lambda: timestamp + 60)
    monkeypatch.setattr(
        "app.services.paddle_webhook_service.record_subscription_event",
        _flaky_record_subscription_event,
    )

    event_id = f"evt_retry_activate_{uuid.uuid4().hex[:8]}"
    payload = _event_payload(
        event_id=event_id,
        event_type="subscription.activated",
        user_id=user.id,
        status="active",
    )
    raw_body, signature = _sign_payload(payload, timestamp, secret)

    try:
        first_response = await client.post(
            "/api/v1/webhooks/paddle",
            content=raw_body,
            headers={"Paddle-Signature": signature, "Content-Type": "application/json"},
        )
    except type(processing_error):
        first_response = None
    if first_response is not None:
        assert first_response.status_code == 500

    webhook_event = (
        (
            await db.execute(
                select(PaddleWebhookEvent).where(PaddleWebhookEvent.event_id == event_id)
            )
        )
        .scalars()
        .one()
    )
    assert webhook_event.processing_status == "failed"
    assert webhook_event.last_error in {
        "transient billing write failure",
        "Something went wrong. Please try again.",
    }

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
        (
            await db.execute(
                select(PaddleWebhookEvent).where(PaddleWebhookEvent.event_id == event_id)
            )
        )
        .scalars()
        .one()
    )
    assert webhook_event.processing_status == "processed"
    assert webhook_event.duplicate_count == 1

    subscription_events = (
        (await db.execute(select(SubscriptionEvent).where(SubscriptionEvent.user_id == user.id)))
        .scalars()
        .all()
    )
    assert [
        event.event_type
        for event in subscription_events
        if event.event_type != "paddle_state_applied"
    ] == ["subscription_activated"]


@pytest.mark.asyncio
async def test_paddle_webhook_subscription_lifecycle_and_transaction_sync(client, db, monkeypatch):
    secret = "pdl_secret_test"
    timestamp = 1_700_000_000
    user = await _create_user(db)

    _patch_service_session(monkeypatch, db)
    monkeypatch.setattr(
        "app.services.paddle_service.settings.PADDLE_WEBHOOK_SECRET", secret, raising=False
    )
    monkeypatch.setattr(
        "app.services.paddle_service.settings.PADDLE_WEBHOOK_TOLERANCE_SECONDS", 300, raising=False
    )
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
        monkeypatch.setattr(
            "app.services.paddle_service.time.time", lambda value=timestamp + index + 60: value
        )
        response = await client.post(
            "/api/v1/webhooks/paddle",
            content=raw_body,
            headers={"Paddle-Signature": signature, "Content-Type": "application/json"},
        )
        assert response.status_code == 200

        await db.refresh(user)
        assert user.tier == expected_tier

    subscription = (
        (await db.execute(select(Subscription).where(Subscription.user_id == user.id)))
        .scalars()
        .one()
    )
    assert subscription.paddle_customer_id == "ctm_123"
    assert subscription.paddle_sub_id == "sub_123"
    assert subscription.paddle_transaction_id == "txn_123"
    assert subscription.status == "canceled"

    subscription_events = (
        (
            await db.execute(
                select(SubscriptionEvent)
                .where(SubscriptionEvent.user_id == user.id)
                .order_by(SubscriptionEvent.occurred_at.asc())
            )
        )
        .scalars()
        .all()
    )
    assert [
        event.event_type
        for event in subscription_events
        if event.event_type != "paddle_state_applied"
    ] == [
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
    monkeypatch.setattr(
        "app.services.paddle_service.settings.PADDLE_WEBHOOK_SECRET", secret, raising=False
    )
    monkeypatch.setattr(
        "app.services.paddle_service.settings.PADDLE_WEBHOOK_TOLERANCE_SECONDS", 300, raising=False
    )
    monkeypatch.setattr("app.services.paddle_service.time.time", lambda: timestamp + 60)

    payload = {
        "event_id": "evt_unknown",
        "event_type": "subscription.foo",
        "data": {"id": "sub_123"},
    }
    raw_body, signature = _sign_payload(payload, timestamp, secret)

    response = await client.post(
        "/api/v1/webhooks/paddle",
        content=raw_body,
        headers={"Paddle-Signature": signature, "Content-Type": "application/json"},
    )

    assert response.status_code == 200
    assert response.json() == {"received": True, "ignored": True}

    webhook_event = (
        (
            await db.execute(
                select(PaddleWebhookEvent).where(PaddleWebhookEvent.event_id == "evt_unknown")
            )
        )
        .scalars()
        .one()
    )
    assert webhook_event.processing_status == "ignored"


@pytest.mark.asyncio
async def test_paddle_webhook_fails_when_supported_event_cannot_be_linked_to_local_user(
    client, db, monkeypatch
):
    secret = "pdl_secret_test"
    timestamp = 1_700_000_000

    _patch_service_session(monkeypatch, db)
    monkeypatch.setattr(
        "app.services.paddle_service.settings.PADDLE_WEBHOOK_SECRET", secret, raising=False
    )
    monkeypatch.setattr(
        "app.services.paddle_service.settings.PADDLE_WEBHOOK_TOLERANCE_SECONDS", 300, raising=False
    )
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
        (
            await db.execute(
                select(PaddleWebhookEvent).where(
                    PaddleWebhookEvent.event_id == "evt_unlinked_paid_event"
                )
            )
        )
        .scalars()
        .one()
    )
    assert webhook_event.processing_status == "failed"


@pytest.mark.asyncio
async def test_paddle_webhook_reclaims_an_expired_processing_lease(client, db, monkeypatch):
    secret = "pdl_secret_test"
    timestamp = 1_700_000_000
    user = await _create_user(db)
    payload = _event_payload(
        event_id="evt_expired_processing_lease",
        event_type="subscription.activated",
        user_id=user.id,
        status="active",
        occurred_at="2026-09-04T10:00:00Z",
    )
    db.add(
        PaddleWebhookEvent(
            event_id=payload["event_id"],
            event_type=payload["event_type"],
            notification_id=payload["notification_id"],
            processing_status="processing",
            payload_json=payload,
            first_received_at=datetime.now(UTC) - timedelta(minutes=10),
            processed_at=datetime.now(UTC) - timedelta(minutes=10),
        )
    )
    await db.commit()

    _patch_service_session(monkeypatch, db)
    monkeypatch.setattr(
        "app.services.paddle_service.settings.PADDLE_WEBHOOK_SECRET", secret, raising=False
    )
    monkeypatch.setattr(
        "app.services.paddle_service.settings.PADDLE_WEBHOOK_TOLERANCE_SECONDS", 300, raising=False
    )
    monkeypatch.setattr("app.services.paddle_service.time.time", lambda: timestamp + 60)
    raw_body, signature = _sign_payload(payload, timestamp, secret)

    response = await client.post(
        "/api/v1/webhooks/paddle",
        content=raw_body,
        headers={"Paddle-Signature": signature, "Content-Type": "application/json"},
    )

    assert response.status_code == 200
    await db.refresh(user)
    assert user.tier == "author"
    webhook_event = await db.scalar(
        select(PaddleWebhookEvent).where(
            PaddleWebhookEvent.event_id == "evt_expired_processing_lease"
        )
    )
    assert webhook_event.processing_status == "processed"
    assert webhook_event.duplicate_count == 1


@pytest.mark.asyncio
async def test_paddle_webhook_ignores_out_of_order_subscription_state(client, db, monkeypatch):
    secret = "pdl_secret_test"
    timestamp = 1_700_000_000
    user = await _create_user(db)

    _patch_service_session(monkeypatch, db)
    monkeypatch.setattr(
        "app.services.paddle_service.settings.PADDLE_WEBHOOK_SECRET", secret, raising=False
    )
    monkeypatch.setattr(
        "app.services.paddle_service.settings.PADDLE_WEBHOOK_TOLERANCE_SECONDS", 300, raising=False
    )

    events = [
        _event_payload(
            event_id="evt_ordered_activation",
            event_type="subscription.activated",
            user_id=user.id,
            status="active",
            occurred_at="2026-09-04T10:00:00Z",
        ),
        _event_payload(
            event_id="evt_ordered_cancellation",
            event_type="subscription.canceled",
            user_id=user.id,
            status="canceled",
            occurred_at="2026-09-04T12:00:00Z",
        ),
        _event_payload(
            event_id="evt_delayed_resume",
            event_type="subscription.resumed",
            user_id=user.id,
            status="active",
            occurred_at="2026-09-04T11:00:00Z",
        ),
    ]

    for index, payload in enumerate(events):
        signed_at = timestamp + index
        monkeypatch.setattr(
            "app.services.paddle_service.time.time",
            lambda value=signed_at + 60: value,
        )
        raw_body, signature = _sign_payload(payload, signed_at, secret)
        response = await client.post(
            "/api/v1/webhooks/paddle",
            content=raw_body,
            headers={"Paddle-Signature": signature, "Content-Type": "application/json"},
        )
        assert response.status_code == 200

    subscription = await db.scalar(select(Subscription).where(Subscription.user_id == user.id))
    await db.refresh(user)
    assert subscription.status == "canceled"
    assert user.tier == "free"
    watermarks = (
        (
            await db.execute(
                select(SubscriptionEvent).where(
                    SubscriptionEvent.user_id == user.id,
                    SubscriptionEvent.event_type == "paddle_state_applied",
                )
            )
        )
        .scalars()
        .all()
    )
    assert [event.occurred_at for event in watermarks] == [
        datetime(2026, 9, 4, 10, tzinfo=UTC),
        datetime(2026, 9, 4, 12, tzinfo=UTC),
    ]


@pytest.mark.asyncio
async def test_transaction_completed_does_not_overwrite_existing_paused_status(
    client, db, monkeypatch
):
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
    monkeypatch.setattr(
        "app.services.paddle_service.settings.PADDLE_WEBHOOK_SECRET", secret, raising=False
    )
    monkeypatch.setattr(
        "app.services.paddle_service.settings.PADDLE_WEBHOOK_TOLERANCE_SECONDS", 300, raising=False
    )
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
        (await db.execute(select(Subscription).where(Subscription.user_id == user.id)))
        .scalars()
        .one()
    )
    assert refreshed_subscription.status == "paused"


@pytest.mark.asyncio
async def test_paddle_webhook_adjustment_approval_updates_refund_review_status(
    client, db, monkeypatch
):
    secret = "pdl_secret_test"
    timestamp = 1_700_000_000
    user = await _create_user(db)
    review = RefundReview(
        user_id=user.id,
        paddle_transaction_id="txn_refund_123",
        paddle_adjustment_id="adj_refund_123",
        charge_at=datetime.now(UTC),
        plan_code="author_monthly",
        billing_interval="monthly",
        request_source="support",
        request_reason="Approved refund",
        status="approved_pending_provider",
        auto_decision=True,
        eligibility_snapshot_json={},
        usage_snapshot_json={},
        provider_response_json={},
    )
    db.add(review)
    await db.commit()

    _patch_service_session(monkeypatch, db)
    monkeypatch.setattr(
        "app.services.paddle_service.settings.PADDLE_WEBHOOK_SECRET", secret, raising=False
    )
    monkeypatch.setattr(
        "app.services.paddle_service.settings.PADDLE_WEBHOOK_TOLERANCE_SECONDS", 300, raising=False
    )
    monkeypatch.setattr("app.services.paddle_service.time.time", lambda: timestamp + 60)

    payload = _adjustment_payload(
        event_id="evt_adjustment_approved",
        transaction_id="txn_refund_123",
        adjustment_id="adj_refund_123",
        status="approved",
    )
    raw_body, signature = _sign_payload(payload, timestamp, secret)

    response = await client.post(
        "/api/v1/webhooks/paddle",
        content=raw_body,
        headers={"Paddle-Signature": signature, "Content-Type": "application/json"},
    )

    assert response.status_code == 200
    await db.refresh(review)
    assert review.status == "approved"
    assert review.paddle_adjustment_id == "adj_refund_123"
    assert review.resolved_at is not None


@pytest.mark.asyncio
async def test_paddle_webhook_adjustment_rejection_leaves_entitlements_unchanged(
    client, db, monkeypatch
):
    secret = "pdl_secret_test"
    timestamp = 1_700_000_000
    user = await _create_user(db)
    user.tier = "author"
    subscription = Subscription(
        user_id=user.id,
        plan="author_monthly",
        status="active",
        paddle_sub_id="sub_reject_123",
        paddle_transaction_id="txn_reject_123",
    )
    db.add(subscription)
    await db.flush()
    review = RefundReview(
        user_id=user.id,
        subscription_id=subscription.id,
        paddle_transaction_id="txn_reject_123",
        paddle_adjustment_id="adj_reject_123",
        charge_at=datetime.now(UTC),
        plan_code="author_monthly",
        billing_interval="monthly",
        request_source="support",
        request_reason="Refund rejection",
        status="approved_pending_provider",
        auto_decision=True,
        eligibility_snapshot_json={},
        usage_snapshot_json={},
        provider_response_json={},
    )
    db.add(review)
    await db.commit()

    _patch_service_session(monkeypatch, db)
    monkeypatch.setattr(
        "app.services.paddle_service.settings.PADDLE_WEBHOOK_SECRET", secret, raising=False
    )
    monkeypatch.setattr(
        "app.services.paddle_service.settings.PADDLE_WEBHOOK_TOLERANCE_SECONDS", 300, raising=False
    )
    monkeypatch.setattr("app.services.paddle_service.time.time", lambda: timestamp + 60)

    payload = _adjustment_payload(
        event_id="evt_adjustment_rejected",
        transaction_id="txn_reject_123",
        adjustment_id="adj_reject_123",
        status="rejected",
    )
    raw_body, signature = _sign_payload(payload, timestamp, secret)

    response = await client.post(
        "/api/v1/webhooks/paddle",
        content=raw_body,
        headers={"Paddle-Signature": signature, "Content-Type": "application/json"},
    )

    assert response.status_code == 200
    await db.refresh(user)
    await db.refresh(review)
    assert user.tier == "author"
    assert review.status == "provider_rejected"


@pytest.mark.asyncio
async def test_refund_adjustment_does_not_downgrade_until_subscription_canceled_webhook(
    client, db, monkeypatch
):
    secret = "pdl_secret_test"
    timestamp = 1_700_000_000
    user = await _create_user(db)
    user.tier = "author"
    subscription = Subscription(
        user_id=user.id,
        plan="author_monthly",
        status="active",
        paddle_customer_id="ctm_cancel_123",
        paddle_sub_id="sub_cancel_123",
        paddle_transaction_id="txn_cancel_123",
    )
    db.add(subscription)
    await db.flush()
    review = RefundReview(
        user_id=user.id,
        subscription_id=subscription.id,
        paddle_transaction_id="txn_cancel_123",
        paddle_adjustment_id="adj_cancel_123",
        charge_at=datetime.now(UTC),
        plan_code="author_monthly",
        billing_interval="monthly",
        request_source="support",
        request_reason="Refund and cancel",
        status="approved_pending_provider",
        auto_decision=True,
        eligibility_snapshot_json={},
        usage_snapshot_json={},
        provider_response_json={},
    )
    db.add(review)
    await db.commit()

    _patch_service_session(monkeypatch, db)
    monkeypatch.setattr(
        "app.services.paddle_service.settings.PADDLE_WEBHOOK_SECRET", secret, raising=False
    )
    monkeypatch.setattr(
        "app.services.paddle_service.settings.PADDLE_WEBHOOK_TOLERANCE_SECONDS", 300, raising=False
    )
    monkeypatch.setattr("app.services.paddle_service.time.time", lambda: timestamp + 60)

    adjustment_payload = _adjustment_payload(
        event_id="evt_adjustment_cancel_approved",
        transaction_id="txn_cancel_123",
        adjustment_id="adj_cancel_123",
        status="approved",
    )
    adjustment_body, adjustment_signature = _sign_payload(adjustment_payload, timestamp, secret)

    adjustment_response = await client.post(
        "/api/v1/webhooks/paddle",
        content=adjustment_body,
        headers={"Paddle-Signature": adjustment_signature, "Content-Type": "application/json"},
    )

    assert adjustment_response.status_code == 200
    await db.refresh(user)
    await db.refresh(review)
    assert user.tier == "author"
    assert review.status == "approved"

    cancel_payload = _event_payload(
        event_id="evt_subscription_cancel_final",
        event_type="subscription.canceled",
        user_id=user.id,
        customer_id="ctm_cancel_123",
        subscription_id="sub_cancel_123",
        transaction_id="txn_cancel_123",
        status="canceled",
    )
    cancel_body, cancel_signature = _sign_payload(cancel_payload, timestamp + 1, secret)
    monkeypatch.setattr("app.services.paddle_service.time.time", lambda: timestamp + 61)

    cancel_response = await client.post(
        "/api/v1/webhooks/paddle",
        content=cancel_body,
        headers={"Paddle-Signature": cancel_signature, "Content-Type": "application/json"},
    )

    assert cancel_response.status_code == 200
    await db.refresh(user)
    assert user.tier == "free"


@pytest.mark.asyncio
async def test_subscription_canceled_webhook_closes_refund_follow_up_after_adjustment_approval(
    client, db, monkeypatch
):
    secret = "pdl_secret_test"
    timestamp = 1_700_000_000
    user = await _create_user(db)
    user.tier = "author"
    subscription = Subscription(
        user_id=user.id,
        plan="author_monthly",
        status="active",
        paddle_customer_id="ctm_followup_close_123",
        paddle_sub_id="sub_followup_close_123",
        paddle_transaction_id="txn_followup_close_123",
    )
    db.add(subscription)
    await db.flush()
    review = RefundReview(
        user_id=user.id,
        subscription_id=subscription.id,
        paddle_transaction_id="txn_followup_close_123",
        paddle_adjustment_id="adj_followup_close_123",
        charge_at=datetime.now(UTC),
        plan_code="author_monthly",
        billing_interval="monthly",
        request_source="support",
        request_reason="Refund and later cancel",
        status="provider_followup_required",
        auto_decision=True,
        eligibility_snapshot_json={},
        usage_snapshot_json={},
        provider_response_json={
            "adjustment_updated": {
                "id": "adj_followup_close_123",
                "action": "refund",
                "status": "approved",
                "transaction_id": "txn_followup_close_123",
            }
        },
    )
    db.add(review)
    await db.commit()

    _patch_service_session(monkeypatch, db)
    monkeypatch.setattr(
        "app.services.paddle_service.settings.PADDLE_WEBHOOK_SECRET", secret, raising=False
    )
    monkeypatch.setattr(
        "app.services.paddle_service.settings.PADDLE_WEBHOOK_TOLERANCE_SECONDS", 300, raising=False
    )
    monkeypatch.setattr("app.services.paddle_service.time.time", lambda: timestamp + 60)

    cancel_payload = _event_payload(
        event_id="evt_subscription_cancel_followup_close",
        event_type="subscription.canceled",
        user_id=user.id,
        customer_id="ctm_followup_close_123",
        subscription_id="sub_followup_close_123",
        transaction_id="txn_followup_close_123",
        status="canceled",
    )
    cancel_body, cancel_signature = _sign_payload(cancel_payload, timestamp, secret)

    cancel_response = await client.post(
        "/api/v1/webhooks/paddle",
        content=cancel_body,
        headers={"Paddle-Signature": cancel_signature, "Content-Type": "application/json"},
    )

    assert cancel_response.status_code == 200
    await db.refresh(user)
    await db.refresh(review)
    assert user.tier == "free"
    assert review.status == "approved"
    assert review.resolved_at is not None


async def _post_signed_event(
    client,
    payload: dict,
    *,
    timestamp: int,
    secret: str = "pdl_secret_test",
) -> object:
    raw_body, signature = _sign_payload(payload, timestamp, secret)
    return await client.post(
        "/api/v1/webhooks/paddle",
        content=raw_body,
        headers={"Paddle-Signature": signature, "Content-Type": "application/json"},
    )


def _configure_webhook_test(monkeypatch, db, secret: str, timestamp: int) -> None:
    _patch_service_session(monkeypatch, db)
    monkeypatch.setattr(
        "app.services.paddle_service.settings.PADDLE_WEBHOOK_SECRET", secret, raising=False
    )
    monkeypatch.setattr(
        "app.services.paddle_service.settings.PADDLE_WEBHOOK_TOLERANCE_SECONDS", 300, raising=False
    )
    monkeypatch.setattr("app.services.paddle_service.time.time", lambda: timestamp + 60)


async def _latest_subscription(db, user_id) -> Subscription:
    return (
        (await db.execute(select(Subscription).where(Subscription.user_id == user_id)))
        .scalars()
        .one()
    )


@pytest.mark.asyncio
async def test_subscription_created_persists_billing_period_and_plan(client, db, monkeypatch):
    secret = "pdl_secret_test"
    timestamp = 1_700_000_000
    user = await _create_user(db)
    _configure_webhook_test(monkeypatch, db, secret, timestamp)

    payload = _event_payload(
        event_id="evt_period_created",
        event_type="subscription.created",
        user_id=user.id,
        status="active",
        billing_period=("2026-09-19T00:00:00Z", "2026-10-19T00:00:00Z"),
    )
    response = await _post_signed_event(client, payload, timestamp=timestamp)

    assert response.status_code == 200
    subscription = await _latest_subscription(db, user.id)
    await db.refresh(subscription)
    assert subscription.plan == "author_annual"
    assert subscription.status == "active"
    assert subscription.current_period_start == datetime(2026, 9, 19, tzinfo=UTC)
    assert subscription.current_period_end == datetime(2026, 10, 19, tzinfo=UTC)
    assert subscription.cancel_at_period_end is False


@pytest.mark.asyncio
async def test_scheduled_cancellation_keeps_paid_access_until_period_end(client, db, monkeypatch):
    secret = "pdl_secret_test"
    timestamp = 1_700_000_000
    user = await _create_user(db)
    sent_cancellations: list[tuple[str, str]] = []

    async def _fake_send_subscription_cancellation(email: str, plan: str) -> None:
        sent_cancellations.append((email, plan))

    _configure_webhook_test(monkeypatch, db, secret, timestamp)
    monkeypatch.setattr(
        "app.services.paddle_webhook_service.send_subscription_cancellation",
        _fake_send_subscription_cancellation,
    )

    activated = _event_payload(
        event_id="evt_scheduled_cancel_activate",
        event_type="subscription.activated",
        user_id=user.id,
        status="active",
        billing_period=("2026-09-19T00:00:00Z", "2026-10-19T00:00:00Z"),
    )
    await _post_signed_event(client, activated, timestamp=timestamp)

    scheduled = _event_payload(
        event_id="evt_scheduled_cancel_update",
        event_type="subscription.updated",
        user_id=user.id,
        status="active",
        billing_period=("2026-09-19T00:00:00Z", "2026-10-19T00:00:00Z"),
        scheduled_change={
            "action": "cancel",
            "effective_at": "2026-10-19T00:00:00Z",
            "resume_at": None,
        },
    )
    response = await _post_signed_event(client, scheduled, timestamp=timestamp + 1)

    assert response.status_code == 200
    await db.refresh(user)
    subscription = await _latest_subscription(db, user.id)
    await db.refresh(subscription)
    assert user.tier == "author"
    assert subscription.plan == "author_annual"
    assert subscription.status == "active"
    assert subscription.cancel_at_period_end is True
    assert subscription.cancellation_scheduled_at == datetime(2026, 10, 19, tzinfo=UTC)
    assert sent_cancellations == []


@pytest.mark.asyncio
async def test_final_cancellation_downgrades_and_clears_scheduled_cancellation(
    client, db, monkeypatch
):
    secret = "pdl_secret_test"
    timestamp = 1_700_000_000
    user = await _create_user(db)
    sent_cancellations: list[tuple[str, str]] = []

    async def _fake_send_subscription_cancellation(email: str, plan: str) -> None:
        sent_cancellations.append((email, plan))

    _configure_webhook_test(monkeypatch, db, secret, timestamp)
    monkeypatch.setattr(
        "app.services.paddle_webhook_service.send_subscription_cancellation",
        _fake_send_subscription_cancellation,
    )

    activated = _event_payload(
        event_id="evt_final_cancel_activate",
        event_type="subscription.activated",
        user_id=user.id,
        status="active",
        billing_period=("2026-09-19T00:00:00Z", "2026-10-19T00:00:00Z"),
    )
    await _post_signed_event(client, activated, timestamp=timestamp)

    scheduled = _event_payload(
        event_id="evt_final_cancel_scheduled",
        event_type="subscription.canceled",
        user_id=user.id,
        status="active",
        billing_period=("2026-09-19T00:00:00Z", "2026-10-19T00:00:00Z"),
    )
    await _post_signed_event(client, scheduled, timestamp=timestamp + 1)

    final = _event_payload(
        event_id="evt_final_cancel_applied",
        event_type="subscription.canceled",
        user_id=user.id,
        status="canceled",
        billing_period=("2026-09-19T00:00:00Z", "2026-10-19T00:00:00Z"),
    )
    response = await _post_signed_event(client, final, timestamp=timestamp + 2)

    assert response.status_code == 200
    await db.refresh(user)
    subscription = await _latest_subscription(db, user.id)
    await db.refresh(subscription)
    assert user.tier == "free"
    assert subscription.status == "canceled"
    assert subscription.plan == "free"
    assert subscription.cancel_at_period_end is False
    assert sent_cancellations == [(user.email, "author")]


@pytest.mark.asyncio
async def test_successful_renewal_advances_billing_period_without_duplicate_confirmation(
    client, db, monkeypatch
):
    secret = "pdl_secret_test"
    timestamp = 1_700_000_000
    user = await _create_user(db)
    sent_confirmations: list[tuple[str, str]] = []

    async def _fake_send_subscription_confirmation(email: str, plan: str) -> None:
        sent_confirmations.append((email, plan))

    _configure_webhook_test(monkeypatch, db, secret, timestamp)
    monkeypatch.setattr(
        "app.services.paddle_webhook_service.send_subscription_confirmation",
        _fake_send_subscription_confirmation,
    )

    activated = _event_payload(
        event_id="evt_renew_activate",
        event_type="subscription.activated",
        user_id=user.id,
        status="active",
        billing_period=("2026-09-19T00:00:00Z", "2026-10-19T00:00:00Z"),
    )
    await _post_signed_event(client, activated, timestamp=timestamp)
    assert sent_confirmations == []

    renewal = _event_payload(
        event_id="evt_renew_update",
        event_type="subscription.updated",
        user_id=user.id,
        status="active",
        billing_period=("2026-10-19T00:00:00Z", "2026-11-19T00:00:00Z"),
    )
    await _post_signed_event(client, renewal, timestamp=timestamp + 1)

    subscription = await _latest_subscription(db, user.id)
    await db.refresh(subscription)
    assert subscription.current_period_start == datetime(2026, 10, 19, tzinfo=UTC)
    assert subscription.current_period_end == datetime(2026, 11, 19, tzinfo=UTC)
    await db.refresh(user)
    assert user.tier == "author"
    assert sent_confirmations == []


@pytest.mark.asyncio
async def test_payment_failure_queues_one_notice_and_keeps_paid_access(client, db, monkeypatch):
    secret = "pdl_secret_test"
    timestamp = 1_700_000_000
    user = await _create_user(db)
    sent_payment_failures: list[tuple[str, str, str | None]] = []

    async def _fake_send_payment_failed(
        email: str, plan: str, *, amount: str | None = None
    ) -> bool:
        sent_payment_failures.append((email, plan, amount))
        return True

    _configure_webhook_test(monkeypatch, db, secret, timestamp)
    monkeypatch.setattr(
        "app.services.paddle_webhook_service.send_subscription_payment_failed",
        _fake_send_payment_failed,
    )

    activated = _event_payload(
        event_id="evt_payment_fail_activate",
        event_type="subscription.activated",
        user_id=user.id,
        status="active",
        billing_period=("2026-09-19T00:00:00Z", "2026-10-19T00:00:00Z"),
    )
    await _post_signed_event(client, activated, timestamp=timestamp)

    failed = _event_payload(
        event_id="evt_payment_fail_txn",
        event_type="transaction.payment_failed",
        user_id=user.id,
        status="past_due",
        billing_period=("2026-09-19T00:00:00Z", "2026-10-19T00:00:00Z"),
        total_minor="1900",
    )
    await _post_signed_event(client, failed, timestamp=timestamp + 1)

    # A second Paddle event for the same billing period must not send again.
    past_due = _event_payload(
        event_id="evt_payment_fail_sub",
        event_type="subscription.past_due",
        user_id=user.id,
        status="past_due",
        billing_period=("2026-09-19T00:00:00Z", "2026-10-19T00:00:00Z"),
    )
    await _post_signed_event(client, past_due, timestamp=timestamp + 2)

    await db.refresh(user)
    subscription = await _latest_subscription(db, user.id)
    await db.refresh(subscription)
    assert user.tier == "author"
    assert subscription.status == "past_due"
    assert subscription.last_payment_status == "failed"
    assert sent_payment_failures == [(user.email, "author_annual", "USD 19.00")]

    email_events = (
        (
            await db.execute(
                select(SubscriptionEmailEvent).where(
                    SubscriptionEmailEvent.subscription_id == subscription.id,
                    SubscriptionEmailEvent.email_type == SUBSCRIPTION_EMAIL_PAYMENT_FAILED,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(email_events) == 1
    assert email_events[0].status == "sent"


@pytest.mark.asyncio
async def test_payment_recovery_returns_subscription_to_active(client, db, monkeypatch):
    secret = "pdl_secret_test"
    timestamp = 1_700_000_000
    user = await _create_user(db)
    _configure_webhook_test(monkeypatch, db, secret, timestamp)

    activated = _event_payload(
        event_id="evt_recover_activate",
        event_type="subscription.activated",
        user_id=user.id,
        status="active",
        billing_period=("2026-09-19T00:00:00Z", "2026-10-19T00:00:00Z"),
    )
    await _post_signed_event(client, activated, timestamp=timestamp)

    failed = _event_payload(
        event_id="evt_recover_fail",
        event_type="transaction.payment_failed",
        user_id=user.id,
        status="past_due",
        billing_period=("2026-09-19T00:00:00Z", "2026-10-19T00:00:00Z"),
    )
    await _post_signed_event(client, failed, timestamp=timestamp + 1)

    recovered = _event_payload(
        event_id="evt_recover_completed",
        event_type="transaction.completed",
        user_id=user.id,
        status="completed",
        billing_period=("2026-09-19T00:00:00Z", "2026-10-19T00:00:00Z"),
        total_minor="1900",
    )
    response = await _post_signed_event(client, recovered, timestamp=timestamp + 2)

    assert response.status_code == 200
    await db.refresh(user)
    subscription = await _latest_subscription(db, user.id)
    await db.refresh(subscription)
    assert user.tier == "author"
    assert subscription.status == "active"
    assert subscription.last_payment_status == "succeeded"


@pytest.mark.asyncio
async def test_deleted_account_webhook_does_not_restore_paid_access(client, db, monkeypatch):
    secret = "pdl_secret_test"
    timestamp = 1_700_000_000
    user = await _create_user(db)
    user.tier = "free"
    user.deletion_status = "deleted"
    user.deleted_at = datetime.now(UTC)
    await db.commit()
    sent_confirmations: list[tuple[str, str]] = []

    async def _fake_send_subscription_confirmation(email: str, plan: str) -> None:
        sent_confirmations.append((email, plan))

    _configure_webhook_test(monkeypatch, db, secret, timestamp)
    monkeypatch.setattr(
        "app.services.paddle_webhook_service.send_subscription_confirmation",
        _fake_send_subscription_confirmation,
    )

    payload = _event_payload(
        event_id="evt_deleted_account_activate",
        event_type="subscription.activated",
        user_id=user.id,
        status="active",
        billing_period=("2026-09-19T00:00:00Z", "2026-10-19T00:00:00Z"),
    )
    response = await _post_signed_event(client, payload, timestamp=timestamp)

    assert response.status_code == 200
    await db.refresh(user)
    assert user.tier == "free"
    assert sent_confirmations == []


def _patch_renewal_email(monkeypatch) -> list[tuple[str, str, str | None, datetime | None]]:
    deliveries: list[tuple[str, str, str | None, datetime | None]] = []

    async def _fake_send_renewal_succeeded(
        email: str,
        plan: str,
        *,
        amount: str | None = None,
        current_period_end: datetime | None = None,
    ) -> bool:
        deliveries.append((email, plan, amount, current_period_end))
        return True

    monkeypatch.setattr(
        "app.services.paddle_webhook_service.send_subscription_renewal_succeeded",
        _fake_send_renewal_succeeded,
    )
    return deliveries


async def _activate_subscription(
    client,
    *,
    timestamp: int,
    user_id,
    event_id: str,
    period: tuple[str, str],
    origin: str | None = None,
) -> None:
    payload = _event_payload(
        event_id=event_id,
        event_type="subscription.activated",
        user_id=user_id,
        status="active",
        billing_period=period,
        origin=origin,
    )
    response = await _post_signed_event(client, payload, timestamp=timestamp)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_initial_purchase_sends_confirmation_not_renewal_email(client, db, monkeypatch):
    secret = "pdl_secret_test"
    timestamp = 1_700_000_000
    user = await _create_user(db)
    sent_confirmations: list[tuple[str, str]] = []

    async def _fake_send_subscription_confirmation(email: str, plan: str) -> None:
        sent_confirmations.append((email, plan))

    _configure_webhook_test(monkeypatch, db, secret, timestamp)
    monkeypatch.setattr(
        "app.services.paddle_webhook_service.send_subscription_confirmation",
        _fake_send_subscription_confirmation,
    )
    renewal_deliveries = _patch_renewal_email(monkeypatch)

    initial = _event_payload(
        event_id="evt_initial_purchase",
        event_type="transaction.completed",
        user_id=user.id,
        status="completed",
        billing_period=("2026-09-19T00:00:00Z", "2026-10-19T00:00:00Z"),
        total_minor="1900",
        origin="api",
    )
    response = await _post_signed_event(client, initial, timestamp=timestamp)

    assert response.status_code == 200
    assert sent_confirmations == [(user.email, "author")]
    assert renewal_deliveries == []
    renewal_rows = (
        (
            await db.execute(
                select(SubscriptionEmailEvent).where(
                    SubscriptionEmailEvent.user_id == user.id,
                    SubscriptionEmailEvent.email_type == SUBSCRIPTION_EMAIL_RENEWAL_SUCCEEDED,
                )
            )
        )
        .scalars()
        .all()
    )
    assert renewal_rows == []


@pytest.mark.asyncio
async def test_recurring_renewal_sends_one_success_email_with_actual_amount(
    client, db, monkeypatch
):
    secret = "pdl_secret_test"
    timestamp = 1_700_000_000
    user = await _create_user(db)
    _configure_webhook_test(monkeypatch, db, secret, timestamp)
    renewal_deliveries = _patch_renewal_email(monkeypatch)

    await _activate_subscription(
        client,
        timestamp=timestamp,
        user_id=user.id,
        event_id="evt_renewal_activate",
        period=("2026-09-19T00:00:00Z", "2026-10-19T00:00:00Z"),
    )

    renewal = _event_payload(
        event_id="evt_renewal_completed",
        event_type="transaction.completed",
        user_id=user.id,
        status="completed",
        billing_period=("2026-10-19T00:00:00Z", "2026-11-19T00:00:00Z"),
        total_minor="1900",
        origin="subscription_recurring",
    )
    response = await _post_signed_event(client, renewal, timestamp=timestamp + 1)

    assert response.status_code == 200
    assert renewal_deliveries == [
        (
            user.email,
            "author_annual",
            "USD 19.00",
            datetime(2026, 11, 19, tzinfo=UTC),
        )
    ]

    email_events = (
        (
            await db.execute(
                select(SubscriptionEmailEvent).where(
                    SubscriptionEmailEvent.user_id == user.id,
                    SubscriptionEmailEvent.email_type == SUBSCRIPTION_EMAIL_RENEWAL_SUCCEEDED,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(email_events) == 1
    assert email_events[0].status == "sent"
    assert email_events[0].metadata_json["transaction_id"] == "txn_123"

    # A distinct duplicate event for the same renewal must not send again.
    duplicate = _event_payload(
        event_id="evt_renewal_completed_duplicate",
        event_type="transaction.completed",
        user_id=user.id,
        status="completed",
        billing_period=("2026-10-19T00:00:00Z", "2026-11-19T00:00:00Z"),
        total_minor="1900",
        origin="subscription_recurring",
    )
    duplicate_response = await _post_signed_event(client, duplicate, timestamp=timestamp + 2)

    assert duplicate_response.status_code == 200
    assert len(renewal_deliveries) == 1
    email_events = (
        (
            await db.execute(
                select(SubscriptionEmailEvent).where(
                    SubscriptionEmailEvent.user_id == user.id,
                    SubscriptionEmailEvent.email_type == SUBSCRIPTION_EMAIL_RENEWAL_SUCCEEDED,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(email_events) == 1


@pytest.mark.asyncio
async def test_failed_renewal_sends_failure_email_not_renewal_success(client, db, monkeypatch):
    secret = "pdl_secret_test"
    timestamp = 1_700_000_000
    user = await _create_user(db)
    sent_payment_failures: list[str] = []

    async def _fake_send_payment_failed(
        email: str, plan: str, *, amount: str | None = None
    ) -> bool:
        sent_payment_failures.append(email)
        return True

    _configure_webhook_test(monkeypatch, db, secret, timestamp)
    monkeypatch.setattr(
        "app.services.paddle_webhook_service.send_subscription_payment_failed",
        _fake_send_payment_failed,
    )
    renewal_deliveries = _patch_renewal_email(monkeypatch)

    await _activate_subscription(
        client,
        timestamp=timestamp,
        user_id=user.id,
        event_id="evt_failed_renewal_activate",
        period=("2026-09-19T00:00:00Z", "2026-10-19T00:00:00Z"),
    )

    failed = _event_payload(
        event_id="evt_failed_renewal_txn",
        event_type="transaction.payment_failed",
        user_id=user.id,
        status="past_due",
        billing_period=("2026-09-19T00:00:00Z", "2026-10-19T00:00:00Z"),
        total_minor="1900",
        origin="subscription_recurring",
    )
    response = await _post_signed_event(client, failed, timestamp=timestamp + 1)

    assert response.status_code == 200
    assert sent_payment_failures == [user.email]
    assert renewal_deliveries == []
    renewal_rows = (
        (
            await db.execute(
                select(SubscriptionEmailEvent).where(
                    SubscriptionEmailEvent.user_id == user.id,
                    SubscriptionEmailEvent.email_type == SUBSCRIPTION_EMAIL_RENEWAL_SUCCEEDED,
                )
            )
        )
        .scalars()
        .all()
    )
    assert renewal_rows == []


@pytest.mark.asyncio
async def test_recovered_renewal_sends_one_success_email_and_reactivates(client, db, monkeypatch):
    secret = "pdl_secret_test"
    timestamp = 1_700_000_000
    user = await _create_user(db)
    _configure_webhook_test(monkeypatch, db, secret, timestamp)
    renewal_deliveries = _patch_renewal_email(monkeypatch)

    await _activate_subscription(
        client,
        timestamp=timestamp,
        user_id=user.id,
        event_id="evt_recovered_renewal_activate",
        period=("2026-09-19T00:00:00Z", "2026-10-19T00:00:00Z"),
    )

    failed = _event_payload(
        event_id="evt_recovered_renewal_failed",
        event_type="transaction.payment_failed",
        user_id=user.id,
        status="past_due",
        billing_period=("2026-09-19T00:00:00Z", "2026-10-19T00:00:00Z"),
        total_minor="1900",
        origin="subscription_recurring",
    )
    await _post_signed_event(client, failed, timestamp=timestamp + 1)

    recovered = _event_payload(
        event_id="evt_recovered_renewal_completed",
        event_type="transaction.completed",
        user_id=user.id,
        status="completed",
        billing_period=("2026-09-19T00:00:00Z", "2026-10-19T00:00:00Z"),
        total_minor="1900",
        origin="subscription_recurring",
    )
    response = await _post_signed_event(client, recovered, timestamp=timestamp + 2)

    assert response.status_code == 200
    await db.refresh(user)
    subscription = await _latest_subscription(db, user.id)
    await db.refresh(subscription)
    assert user.tier == "author"
    assert subscription.status == "active"
    assert len(renewal_deliveries) == 1
    assert renewal_deliveries[0][2] == "USD 19.00"
