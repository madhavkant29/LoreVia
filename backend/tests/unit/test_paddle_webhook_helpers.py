from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.services import paddle_webhook_service as service


@pytest.mark.parametrize(
    ("event_type", "incoming", "current", "expected"),
    [
        ("transaction.completed", "", "pending", "active"),
        ("transaction.completed", "", "paused", "paused"),
        ("transaction.past_due", "", "active", "past_due"),
        ("transaction.payment_failed", "failed", "active", "failed"),
        ("transaction.payment_failed", "", "active", "past_due"),
        ("subscription.activated", "", "pending", "active"),
        ("subscription.resumed", "", "paused", "active"),
        ("subscription.trialing", "", "pending", "trialing"),
        ("subscription.paused", "", "active", "paused"),
        ("subscription.past_due", "", "active", "past_due"),
        ("subscription.canceled", "cancelled", "active", "cancelled"),
        ("subscription.canceled", "", "active", "canceled"),
        ("subscription.created", "trialing", "", "trialing"),
        ("subscription.created", "", "", "pending"),
        ("subscription.updated", "active", "pending", "active"),
        ("transaction.updated", "", "active", "active"),
        ("unknown", "", "", "pending"),
    ],
)
def test_next_subscription_status_covers_provider_lifecycle(
    event_type, incoming, current, expected
):
    assert (
        service._next_subscription_status(
            event_type=event_type,
            incoming_status=incoming,
            current_status=current,
        )
        == expected
    )


def test_paddle_identifier_and_normalization_helpers_cover_nested_and_empty_values():
    assert (
        service._subscription_id_from_data(
            event_type="subscription.updated", data={"id": " sub-1 "}
        )
        == "sub-1"
    )
    assert (
        service._subscription_id_from_data(
            event_type="transaction.completed", data={"subscription": {"id": "sub-2"}}
        )
        == "sub-2"
    )
    assert service._customer_id_from_data({"customer": {"id": "customer-1"}}) == "customer-1"
    assert (
        service._transaction_id_from_data(event_type="transaction.completed", data={"id": "txn-1"})
        == "txn-1"
    )
    assert (
        service._transaction_id_from_data(
            event_type="subscription.updated", data={"transaction": {"id": "txn-2"}}
        )
        == "txn-2"
    )
    assert service._normalized_status(" Active ") == "active"
    assert service._string_or_none("  ") is None
    assert service._string_or_none(42) == "42"
    assert service._is_service_active("TRIALING") is True
    assert service._is_service_active(None) is False
    assert service._event_occurred_at({"occurred_at": "2026-09-04T10:30:00Z"}) == datetime(
        2026, 9, 4, 10, 30, tzinfo=UTC
    )
    assert service._event_occurred_at({"occurred_at": "not-a-date"}) is None


def test_tier_and_metrics_helpers_preserve_or_change_access_by_event(monkeypatch):
    monkeypatch.setattr(service, "tier_from_plan_code", lambda plan, price: "architect")
    monkeypatch.setattr(
        service,
        "subscription_service_is_active",
        lambda event, status: status in {"active", "trialing"},
    )

    assert (
        service._tier_after_event(
            event_type="subscription.paused",
            status="paused",
            plan="pro",
            price_id="p",
            current_tier="author",
        )
        == "free"
    )
    assert (
        service._tier_after_event(
            event_type="subscription.canceled",
            status="canceled",
            plan="pro",
            price_id="p",
            current_tier="author",
        )
        == "free"
    )
    assert (
        service._tier_after_event(
            event_type="subscription.canceled",
            status="active",
            plan="pro",
            price_id="p",
            current_tier="author",
        )
        == "author"
    )
    assert (
        service._tier_after_event(
            event_type="transaction.past_due",
            status="past_due",
            plan="pro",
            price_id="p",
            current_tier="author",
        )
        == "author"
    )
    assert (
        service._tier_after_event(
            event_type="subscription.activated",
            status="active",
            plan="pro",
            price_id="p",
            current_tier="free",
        )
        == "architect"
    )
    assert (
        service._tier_after_event(
            event_type="subscription.created",
            status="pending",
            plan="pro",
            price_id="p",
            current_tier="free",
        )
        == "free"
    )

    monkeypatch.setattr(
        service,
        "subscription_event_type_for_metrics",
        lambda event, status: "subscription_activated",
    )
    assert (
        service._metrics_event_type(
            event_type="subscription.canceled", previous_status="active", status="pending"
        )
        is None
    )
    assert (
        service._metrics_event_type(
            event_type="subscription.activated", previous_status="active", status="active"
        )
        is None
    )
    assert (
        service._metrics_event_type(
            event_type="subscription.activated", previous_status="pending", status="pending"
        )
        is None
    )
    assert (
        service._metrics_event_type(
            event_type="subscription.activated", previous_status="pending", status="active"
        )
        == "subscription_activated"
    )


class FakeResult:
    def __init__(self, value):
        self.value = value

    def scalars(self):
        return self

    def first(self):
        return self.value


class FakeDb:
    def __init__(self, value):
        self.value = value

    async def execute(self, _statement):
        return FakeResult(self.value)


@pytest.mark.asyncio
async def test_refund_follow_up_resolves_only_approved_adjustment_cancellation():
    review = SimpleNamespace(
        status=service.REFUND_STATUS_PROVIDER_FOLLOWUP_REQUIRED,
        paddle_adjustment_id="adj-1",
        provider_response_json={"adjustment_updated": {"status": " APPROVED "}},
        resolved_at=None,
    )

    await service._resolve_refund_follow_up_if_completed_cancellation(
        FakeDb(review),
        event_type="subscription.canceled",
        status="canceled",
        transaction_id="txn-1",
    )

    assert review.status == service.REFUND_STATUS_APPROVED
    assert isinstance(review.resolved_at, datetime)
    assert review.resolved_at.tzinfo == UTC

    untouched = SimpleNamespace(
        status=service.REFUND_STATUS_PROVIDER_FOLLOWUP_REQUIRED,
        paddle_adjustment_id="adj-2",
        provider_response_json={"adjustment_updated": {"status": "pending"}},
        resolved_at=None,
    )
    await service._resolve_refund_follow_up_if_completed_cancellation(
        FakeDb(untouched),
        event_type="subscription.canceled",
        status="canceled",
        transaction_id="txn-2",
    )
    assert untouched.status == service.REFUND_STATUS_PROVIDER_FOLLOWUP_REQUIRED
    assert (
        service._review_has_approved_adjustment(
            SimpleNamespace(provider_response_json={"adjustment_updated": "bad"})
        )
        is False
    )

    await service._resolve_refund_follow_up_if_completed_cancellation(
        FakeDb(review),
        event_type="subscription.updated",
        status="active",
        transaction_id=None,
    )


@pytest.mark.asyncio
async def test_process_claimed_webhook_handles_ignored_and_adjustment_events(monkeypatch):
    webhook = SimpleNamespace(
        event_type="",
        notification_id=None,
        payload_json={},
        processing_status="processing",
        processed_at=None,
        last_error="old error",
    )

    class Session:
        commits = 0
        rollbacks = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def commit(self):
            self.commits += 1

        async def rollback(self):
            self.rollbacks += 1

    session = Session()

    async def get_event(_db, _event_id):
        return webhook

    monkeypatch.setattr(service, "AsyncSessionLocal", lambda: session)
    monkeypatch.setattr(service, "_get_webhook_event", get_event)

    ignored = await service._process_claimed_webhook(
        event_id="evt-ignored",
        event_type="unsupported.event",
        notification_id="ntf-1",
        payload={"data": {}},
    )
    assert ignored == {"received": True, "ignored": True}
    assert webhook.processing_status == service.WEBHOOK_STATUS_IGNORED

    applied: list[dict] = []

    async def apply_adjustment(_db, **kwargs):
        applied.append(kwargs)

    monkeypatch.setattr(service, "apply_adjustment_webhook", apply_adjustment)
    processed = await service._process_claimed_webhook(
        event_id="evt-adjustment",
        event_type="adjustment.updated",
        notification_id=None,
        payload={"data": {"id": "adj-1"}},
    )
    assert processed == {"received": True}
    assert applied[0]["data"] == {"id": "adj-1"}
    assert webhook.processing_status == service.WEBHOOK_STATUS_PROCESSED


@pytest.mark.asyncio
async def test_claim_webhook_event_creates_new_processing_record(monkeypatch):
    class Session:
        def __init__(self):
            self.added = []
            self.commits = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        def add(self, item):
            self.added.append(item)

        async def commit(self):
            self.commits += 1

    session = Session()

    async def missing(_db, _event_id):
        return None

    monkeypatch.setattr(service, "AsyncSessionLocal", lambda: session)
    monkeypatch.setattr(service, "_get_webhook_event", missing)

    result = await service._claim_webhook_event(
        event_id="evt-new",
        event_type="subscription.created",
        notification_id="ntf-new",
        payload={"event_id": "evt-new"},
    )
    assert result == {"duplicate": False}
    assert session.added[0].processing_status == service.WEBHOOK_STATUS_PROCESSING
