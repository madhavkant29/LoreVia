import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.models.book import Book
from app.models.user import AdminPrincipal, RefundReview, Subscription, SubscriptionEvent, User
from app.services.refund_service import (
    CANCEL_SUBSCRIPTION_ERROR_MESSAGE,
    REFUND_STATUS_APPROVED_PENDING_PROVIDER,
    REFUND_STATUS_MANUAL_REVIEW_REQUIRED,
    REFUND_STATUS_PROVIDER_FOLLOWUP_REQUIRED,
)


async def _register_user(client, email: str) -> tuple[dict[str, str], uuid.UUID]:
    from app.core.security import create_access_token
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "username": email.split("@")[0][:24],
            "password": "StrongPass123!@#",
            "accepted_terms": True,
            "device_id": f"device-{uuid.uuid4().hex[:24]}",
        },
    )
    assert response.status_code == 201
    token = create_access_token(str(response.json()["id"]))
    assert token
    me = await client.get("/api/v1/auth/me", headers={"Cookie": f"lorevia_access_token={token}"})
    assert me.status_code == 200
    return {"Authorization": f"Bearer {token}"}, uuid.UUID(me.json()["id"])


async def _grant_admin(
    client,
    db,
    user_id: uuid.UUID,
    headers: dict[str, str],
    *,
    scopes: list[str] | None = None,
    is_owner: bool = True,
) -> None:
    from app.core.redis import store_refresh_session
    from app.core.security import create_refresh_token

    db.add(
        AdminPrincipal(
            user_id=user_id,
            status="active",
            is_owner=is_owner,
            scopes=scopes or ["moderation_admin", "billing_admin", "super_admin"],
            grant_reason="Test admin grant.",
        )
    )
    await db.commit()
    session_id = str(uuid.uuid4())
    await store_refresh_session(str(user_id), session_id, 600)
    refresh_token = create_refresh_token(str(user_id), session_id=session_id)
    headers["Cookie"] = f"lorevia_refresh_token={refresh_token}"
    response = await client.post(
        "/api/v1/admin/step-up",
        json={"password": "StrongPass123!@#"},
        headers=headers,
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_admin_queue_depth_reports_redis_lengths(client, db, monkeypatch):
    headers, user_id = await _register_user(client, f"admin-queue-depth-{uuid.uuid4().hex[:8]}@lorevia.app")
    user = await db.get(User, user_id)
    assert user is not None
    await _grant_admin(client, db, user_id, headers)

    class FakeRedis:
        async def get(self, key: str):
            return None

        async def set(self, key: str, value, ex=None, nx=False):
            return True

        async def exists(self, *keys):
            return 0

        async def incr(self, key: str):
            return 1

        async def llen(self, key: str) -> int:
            return {
                "extraction": 7,
                "analysis": 3,
                "embedding": 11,
                "intelligence": 2,
            }[key]

    fake_redis = FakeRedis()
    monkeypatch.setattr("app.core.redis._redis", fake_redis, raising=False)

    async def fake_get_redis():
        return fake_redis

    monkeypatch.setattr("app.core.redis.get_redis", fake_get_redis, raising=False)

    response = await client.get("/api/v1/admin/queue-depth", headers=headers)

    assert response.status_code == 200
    assert response.json() == {
        "extraction": 7,
        "analysis": 3,
        "embedding": 11,
        "intelligence": 2,
    }


@pytest.mark.asyncio
async def test_admin_subscription_metrics_reports_trial_conversion_and_post_cancel_churn(client, db):
    headers, user_id = await _register_user(client, f"admin-subscription-metrics-{uuid.uuid4().hex[:8]}@lorevia.app")
    admin_user = await db.get(User, user_id)
    assert admin_user is not None
    await _grant_admin(client, db, user_id, headers)

    cohort_start = datetime(2010, 5, 1, 9, 0, tzinfo=UTC)
    converted_user = User(
        email=f"metrics-converted-{uuid.uuid4().hex[:8]}@lorevia.app",
        username=f"metricsconv{uuid.uuid4().hex[:8]}",
        password_hash="hash",
        created_at=cohort_start,
    )
    churned_user = User(
        email=f"metrics-churned-{uuid.uuid4().hex[:8]}@lorevia.app",
        username=f"metricschurn{uuid.uuid4().hex[:8]}",
        password_hash="hash",
        created_at=cohort_start + timedelta(days=1),
    )
    reactivated_user = User(
        email=f"metrics-reactivated-{uuid.uuid4().hex[:8]}@lorevia.app",
        username=f"metricsreact{uuid.uuid4().hex[:8]}",
        password_hash="hash",
        created_at=cohort_start + timedelta(days=2),
    )
    db.add_all([converted_user, churned_user, reactivated_user])
    await db.flush()

    db.add_all(
        [
            SubscriptionEvent(
                user_id=converted_user.id,
                event_type="subscription_activated",
                source="paddle",
                source_event_id=f"evt-convert-{uuid.uuid4().hex}",
                plan="author_monthly",
                status="active",
                occurred_at=cohort_start + timedelta(days=4),
            ),
            SubscriptionEvent(
                user_id=churned_user.id,
                event_type="subscription_canceled",
                source="paddle",
                source_event_id=f"evt-churn-{uuid.uuid4().hex}",
                plan="author_monthly",
                status="canceled",
                occurred_at=cohort_start + timedelta(days=5),
            ),
            SubscriptionEvent(
                user_id=reactivated_user.id,
                event_type="subscription_canceled",
                source="paddle",
                source_event_id=f"evt-cancel-{uuid.uuid4().hex}",
                plan="author_monthly",
                status="canceled",
                occurred_at=cohort_start + timedelta(days=5),
            ),
            SubscriptionEvent(
                user_id=reactivated_user.id,
                event_type="subscription_activated",
                source="paddle",
                source_event_id=f"evt-reactivate-{uuid.uuid4().hex}",
                plan="author_monthly",
                status="active",
                occurred_at=cohort_start + timedelta(days=10),
            ),
        ]
    )
    await db.commit()

    response = await client.get(
        "/api/v1/admin/subscription-metrics?start_date=2010-05-01&end_date=2010-05-31&reactivation_window_days=3",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json() == {
        "cohort_start": "2010-05-01",
        "cohort_end": "2010-05-31",
        "trial_starts": 3,
        "trial_to_paid_conversions": 2,
        "trial_to_paid_rate": 66.67,
        "cancellation_events": 2,
        "resolved_cancellation_events": 2,
        "unresolved_cancellation_events": 0,
        "reactivated_after_cancellation": 0,
        "churned_after_cancellation": 2,
        "post_cancel_churn_rate": 100.0,
        "reactivation_window_days": 3,
    }


@pytest.mark.asyncio
async def test_admin_public_demo_routes_require_moderation_scope_and_old_public_write_paths_are_gone(client, db):
    headers, user_id = await _register_user(client, f"admin-public-demo-scope-{uuid.uuid4().hex[:8]}@lorevia.app")
    user = await db.get(User, user_id)
    assert user is not None
    await _grant_admin(client, db, user_id, headers, scopes=["billing_admin"], is_owner=False)

    admin_response = await client.post(
        "/api/v1/admin/public-books/manual",
        json={
            "title": "Demo Book",
            "author": "LoreVia",
            "description": "Internal public demo.",
            "chapters": [{"title": "Chapter 1", "text": "Once upon a time."}],
        },
        headers=headers,
    )
    legacy_response = await client.post(
        "/api/v1/public/books/manual",
        json={
            "title": "Demo Book",
            "author": "LoreVia",
            "description": "Internal public demo.",
            "chapters": [{"title": "Chapter 1", "text": "Once upon a time."}],
        },
        headers=headers,
    )

    assert admin_response.status_code == 403
    assert legacy_response.status_code in {404, 405}


@pytest.mark.asyncio
async def test_admin_can_create_and_append_public_demo_books_only_through_admin_routes(client, db):
    headers, user_id = await _register_user(client, f"admin-public-demo-{uuid.uuid4().hex[:8]}@lorevia.app")
    user = await db.get(User, user_id)
    assert user is not None
    await _grant_admin(client, db, user_id, headers, scopes=["moderation_admin"], is_owner=False)

    create_response = await client.post(
        "/api/v1/admin/public-books/manual",
        json={
            "title": "Ash Gate Demo",
            "author": "M. Vale",
            "genre": "Fantasy",
            "description": "Safe internal public demo.",
            "chapters": [
                {"title": "The Gate Opens", "text": "Nora crossed the ash gate.", "description": "Opening beat."},
            ],
        },
        headers=headers,
    )

    assert create_response.status_code == 200
    payload = create_response.json()
    assert payload["public_kind"] == "public_demo"
    assert payload["approval_status"] == "approved"
    assert payload["public_slug"] == "ash-gate-demo"

    created_book = await db.get(Book, uuid.UUID(payload["book_id"]))
    assert created_book is not None
    assert created_book.source_kind == "public_demo"
    assert created_book.total_chapters == 1

    append_response = await client.post(
        f"/api/v1/admin/public-books/{payload['book_id']}/chapters",
        json={
            "title": "Ash Bell",
            "text": "The bells answered her name.",
            "description": "Follow-up chapter.",
        },
        headers=headers,
    )

    assert append_response.status_code == 200
    assert append_response.json() == {
        "book_id": payload["book_id"],
        "chapter_number": 2,
        "saved": True,
    }

    legacy_append_response = await client.post(
        f"/api/v1/public/books/{payload['book_id']}/chapters",
        json={
            "title": "Legacy path",
            "text": "This should not work.",
        },
        headers=headers,
    )
    assert legacy_append_response.status_code in {404, 405}

    await db.refresh(created_book)
    assert created_book.total_chapters == 2
    assert created_book.total_tokens is not None


@pytest.mark.asyncio
async def test_admin_refund_review_create_requires_admin(client):
    headers, _user_id = await _register_user(client, f"refund-non-admin-{uuid.uuid4().hex[:8]}@lorevia.app")

    response = await client.post(
        "/api/v1/admin/refunds/reviews",
        json={
            "transaction_id": "txn_123",
            "reason": "Need refund",
            "request_source": "support",
        },
        headers=headers,
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_refund_review_create_auto_submits_eligible_monthly_refund(client, db, monkeypatch):
    admin_headers, admin_user_id = await _register_user(client, f"refund-admin-{uuid.uuid4().hex[:8]}@lorevia.app")
    admin_user = await db.get(User, admin_user_id)
    assert admin_user is not None
    await _grant_admin(client, db, admin_user_id, admin_headers)

    target_user = User(
        email=f"refund-target-{uuid.uuid4().hex[:8]}@lorevia.app",
        username=f"refundtarget{uuid.uuid4().hex[:8]}",
        password_hash="hash",
        tier="author",
        created_at=datetime.now(UTC) - timedelta(days=10),
    )
    db.add(target_user)
    await db.flush()
    subscription = Subscription(
        user_id=target_user.id,
        plan="author_monthly",
        status="active",
        paddle_sub_id="sub_123",
        paddle_transaction_id="txn_123",
    )
    db.add(subscription)
    await db.commit()

    charge_at = datetime.now(UTC) - timedelta(hours=1)

    async def fake_get_transaction_summary(transaction_id: str):
        assert transaction_id == "txn_123"
        return SimpleNamespace(
            transaction_id="txn_123",
            status="completed",
            plan="author_monthly",
            billing_interval="monthly",
            display_name="Author",
            currency_code="USD",
            total="USD 29.00",
            invoice_number="INV-123",
            invoice_pdf_url=None,
            subscription_id="sub_123",
            customer_email=target_user.email,
            customer_id="ctm_123",
            charge_at=charge_at,
        )

    async def fake_create_refund_adjustment(transaction_id: str, reason: str):
        assert transaction_id == "txn_123"
        assert reason == "Accidental monthly renewal"
        return {"id": "adj_123", "status": "pending_approval"}

    async def fake_cancel_subscription_immediately(subscription_id: str):
        assert subscription_id == "sub_123"
        return {"id": "sub_123", "status": "canceled"}

    monkeypatch.setattr("app.services.refund_service.get_transaction_summary", fake_get_transaction_summary)
    monkeypatch.setattr("app.services.refund_service.create_refund_adjustment", fake_create_refund_adjustment)
    monkeypatch.setattr("app.services.refund_service.cancel_subscription_immediately", fake_cancel_subscription_immediately)

    response = await client.post(
        "/api/v1/admin/refunds/reviews",
        json={
            "transaction_id": "txn_123",
            "reason": "Accidental monthly renewal",
            "request_source": "support",
            "support_reference": "CASE-123",
        },
        headers=admin_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == REFUND_STATUS_APPROVED_PENDING_PROVIDER
    assert payload["auto_decision"] is True
    assert payload["paddle_adjustment_id"] == "adj_123"
    assert payload["eligibility_snapshot_json"]["within_auto_refund_window"] is True
    assert payload["usage_snapshot_json"]["has_meaningful_usage"] is False


@pytest.mark.asyncio
async def test_admin_refund_review_create_stores_manual_review_when_usage_exists(client, db, monkeypatch):
    admin_headers, admin_user_id = await _register_user(client, f"refund-manual-admin-{uuid.uuid4().hex[:8]}@lorevia.app")
    admin_user = await db.get(User, admin_user_id)
    assert admin_user is not None
    await _grant_admin(client, db, admin_user_id, admin_headers)

    target_user = User(
        email=f"refund-manual-{uuid.uuid4().hex[:8]}@lorevia.app",
        username=f"refundmanual{uuid.uuid4().hex[:8]}",
        password_hash="hash",
        tier="author",
        created_at=datetime.now(UTC) - timedelta(days=10),
    )
    db.add(target_user)
    await db.flush()
    subscription = Subscription(
        user_id=target_user.id,
        plan="author_monthly",
        status="active",
        paddle_sub_id="sub_manual_123",
        paddle_transaction_id="txn_manual_123",
    )
    db.add(subscription)
    charge_at = datetime.now(UTC) - timedelta(hours=2)
    db.add(
        Book(
            user_id=target_user.id,
            title="Used after purchase",
            format="txt",
            s3_key="books/used-after-purchase.txt",
            status="ready",
            created_at=charge_at + timedelta(minutes=30),
        )
    )
    await db.commit()

    async def fake_get_transaction_summary(transaction_id: str):
        assert transaction_id == "txn_manual_123"
        return SimpleNamespace(
            transaction_id="txn_manual_123",
            status="completed",
            plan="author_monthly",
            billing_interval="monthly",
            display_name="Author",
            currency_code="USD",
            total="USD 29.00",
            invoice_number="INV-456",
            invoice_pdf_url=None,
            subscription_id="sub_manual_123",
            customer_email=target_user.email,
            customer_id="ctm_manual_123",
            charge_at=charge_at,
        )

    async def fail_create_refund_adjustment(*args, **kwargs):
        raise AssertionError("Provider refund creation should not run for manual-review cases")

    monkeypatch.setattr("app.services.refund_service.get_transaction_summary", fake_get_transaction_summary)
    monkeypatch.setattr("app.services.refund_service.create_refund_adjustment", fail_create_refund_adjustment)

    response = await client.post(
        "/api/v1/admin/refunds/reviews",
        json={
            "transaction_id": "txn_manual_123",
            "reason": "Charge should be reviewed",
            "request_source": "support",
        },
        headers=admin_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == REFUND_STATUS_MANUAL_REVIEW_REQUIRED
    assert payload["auto_decision"] is False
    assert payload["usage_snapshot_json"]["book_count"] == 1


@pytest.mark.asyncio
async def test_admin_refund_review_manual_approve_and_deny_paths(client, db, monkeypatch):
    admin_headers, admin_user_id = await _register_user(client, f"refund-decision-admin-{uuid.uuid4().hex[:8]}@lorevia.app")
    admin_user = await db.get(User, admin_user_id)
    assert admin_user is not None
    await _grant_admin(client, db, admin_user_id, admin_headers)

    target_user = User(
        email=f"refund-decision-{uuid.uuid4().hex[:8]}@lorevia.app",
        username=f"refunddecision{uuid.uuid4().hex[:8]}",
        password_hash="hash",
        tier="author",
        created_at=datetime.now(UTC) - timedelta(days=10),
    )
    db.add(target_user)
    await db.flush()
    subscription = Subscription(
        user_id=target_user.id,
        plan="author_annual",
        status="active",
        paddle_sub_id="sub_decision_123",
        paddle_transaction_id="txn_decision_123",
    )
    db.add(subscription)
    await db.flush()
    review = RefundReview(
        user_id=target_user.id,
        subscription_id=subscription.id,
        paddle_transaction_id="txn_decision_123",
        charge_at=datetime.now(UTC) - timedelta(hours=1),
        plan_code="author_annual",
        billing_interval="annual",
        request_source="support",
        request_reason="Needs human decision",
        status=REFUND_STATUS_MANUAL_REVIEW_REQUIRED,
        auto_decision=False,
        eligibility_snapshot_json={},
        usage_snapshot_json={},
        provider_response_json={},
        requested_by_admin_user_id=admin_user.id,
    )
    deny_review = RefundReview(
        user_id=target_user.id,
        subscription_id=subscription.id,
        paddle_transaction_id="txn_deny_123",
        charge_at=datetime.now(UTC) - timedelta(hours=3),
        plan_code="author_monthly",
        billing_interval="monthly",
        request_source="support",
        request_reason="Should be denied",
        status=REFUND_STATUS_MANUAL_REVIEW_REQUIRED,
        auto_decision=False,
        eligibility_snapshot_json={},
        usage_snapshot_json={},
        provider_response_json={},
        requested_by_admin_user_id=admin_user.id,
    )
    db.add_all([review, deny_review])
    await db.commit()

    async def fake_create_refund_adjustment(transaction_id: str, reason: str):
        assert transaction_id
        assert reason
        return {"id": "adj_manual_123", "status": "pending_approval"}

    async def fake_cancel_subscription_immediately(subscription_id: str):
        assert subscription_id == "sub_decision_123"
        return {"id": "sub_decision_123", "status": "canceled"}

    monkeypatch.setattr("app.services.refund_service.create_refund_adjustment", fake_create_refund_adjustment)
    monkeypatch.setattr("app.services.refund_service.cancel_subscription_immediately", fake_cancel_subscription_immediately)

    approve_response = await client.post(
        f"/api/v1/admin/refunds/reviews/{review.id}/approve",
        json={"reason": "Manual approval after support review"},
        headers=admin_headers,
    )
    deny_response = await client.post(
        f"/api/v1/admin/refunds/reviews/{deny_review.id}/deny",
        json={"reason": "Not eligible after review"},
        headers=admin_headers,
    )

    assert approve_response.status_code == 200
    assert approve_response.json()["status"] == REFUND_STATUS_APPROVED_PENDING_PROVIDER
    assert approve_response.json()["resolved_by_admin_user_id"] == str(admin_user.id)

    assert deny_response.status_code == 200
    assert deny_response.json()["status"] == "denied"
    assert deny_response.json()["decision_reason"] == "Not eligible after review"
    assert deny_response.json()["resolved_by_admin_user_id"] == str(admin_user.id)


@pytest.mark.asyncio
async def test_admin_refund_review_surfaces_partial_provider_failure_for_follow_up(client, db, monkeypatch):
    admin_headers, admin_user_id = await _register_user(client, f"refund-followup-admin-{uuid.uuid4().hex[:8]}@lorevia.app")
    admin_user = await db.get(User, admin_user_id)
    assert admin_user is not None
    await _grant_admin(client, db, admin_user_id, admin_headers)

    target_user = User(
        email=f"refund-followup-{uuid.uuid4().hex[:8]}@lorevia.app",
        username=f"refundfollowup{uuid.uuid4().hex[:8]}",
        password_hash="hash",
        tier="author",
        created_at=datetime.now(UTC) - timedelta(days=10),
    )
    db.add(target_user)
    await db.flush()
    subscription = Subscription(
        user_id=target_user.id,
        plan="author_monthly",
        status="active",
        paddle_sub_id="sub_followup_123",
        paddle_transaction_id="txn_followup_123",
    )
    db.add(subscription)
    await db.commit()

    charge_at = datetime.now(UTC) - timedelta(hours=1)

    async def fake_get_transaction_summary(transaction_id: str):
        return SimpleNamespace(
            transaction_id=transaction_id,
            status="completed",
            plan="author_monthly",
            billing_interval="monthly",
            display_name="Author",
            currency_code="USD",
            total="USD 29.00",
            invoice_number="INV-FOLLOWUP-123",
            invoice_pdf_url=None,
            subscription_id="sub_followup_123",
            customer_email=target_user.email,
            customer_id="ctm_followup_123",
            charge_at=charge_at,
        )

    async def fake_create_refund_adjustment(transaction_id: str, reason: str):
        return {"id": "adj_followup_123", "status": "pending_approval"}

    async def fail_cancel_subscription_immediately(subscription_id: str):
        raise RuntimeError(
            "provider timeout authorization=Bearer refund-admin-secret "
            "database_url=postgresql://admin_refund:admin_pass@db.example.com/refunds"
        )

    monkeypatch.setattr("app.services.refund_service.get_transaction_summary", fake_get_transaction_summary)
    monkeypatch.setattr("app.services.refund_service.create_refund_adjustment", fake_create_refund_adjustment)
    monkeypatch.setattr("app.services.refund_service.cancel_subscription_immediately", fail_cancel_subscription_immediately)

    response = await client.post(
        "/api/v1/admin/refunds/reviews",
        json={
            "transaction_id": "txn_followup_123",
            "reason": "Refund with provider follow-up",
            "request_source": "support",
        },
        headers=admin_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == REFUND_STATUS_PROVIDER_FOLLOWUP_REQUIRED
    assert payload["paddle_adjustment_id"] == "adj_followup_123"
    assert payload["provider_response_json"]["cancel_subscription_error"] == CANCEL_SUBSCRIPTION_ERROR_MESSAGE
    assert "refund-admin-secret" not in payload["provider_response_json"]["cancel_subscription_error_redacted"]
    assert "admin_pass" not in payload["provider_response_json"]["cancel_subscription_error_redacted"]
    assert "[REDACTED]" in payload["provider_response_json"]["cancel_subscription_error_redacted"]


@pytest.mark.asyncio
async def test_admin_refund_review_deny_rejects_reviews_already_submitted_to_provider(client, db):
    admin_headers, admin_user_id = await _register_user(client, f"refund-deny-admin-{uuid.uuid4().hex[:8]}@lorevia.app")
    admin_user = await db.get(User, admin_user_id)
    assert admin_user is not None
    await _grant_admin(client, db, admin_user_id, admin_headers)

    target_user = User(
        email=f"refund-deny-target-{uuid.uuid4().hex[:8]}@lorevia.app",
        username=f"refunddenytarget{uuid.uuid4().hex[:8]}",
        password_hash="hash",
        tier="author",
        created_at=datetime.now(UTC) - timedelta(days=10),
    )
    db.add(target_user)
    await db.flush()
    subscription = Subscription(
        user_id=target_user.id,
        plan="author_monthly",
        status="active",
        paddle_sub_id="sub_deny_submitted_123",
        paddle_transaction_id="txn_deny_submitted_123",
    )
    db.add(subscription)
    await db.flush()
    pending_provider_review = RefundReview(
        user_id=target_user.id,
        subscription_id=subscription.id,
        paddle_transaction_id="txn_deny_submitted_123",
        paddle_adjustment_id="adj_deny_submitted_123",
        charge_at=datetime.now(UTC) - timedelta(hours=1),
        plan_code="author_monthly",
        billing_interval="monthly",
        request_source="support",
        request_reason="Already submitted",
        status=REFUND_STATUS_APPROVED_PENDING_PROVIDER,
        auto_decision=True,
        eligibility_snapshot_json={},
        usage_snapshot_json={},
        provider_response_json={},
        requested_by_admin_user_id=admin_user.id,
    )
    followup_review = RefundReview(
        user_id=target_user.id,
        subscription_id=subscription.id,
        paddle_transaction_id="txn_deny_followup_123",
        paddle_adjustment_id="adj_deny_followup_123",
        charge_at=datetime.now(UTC) - timedelta(hours=2),
        plan_code="author_monthly",
        billing_interval="monthly",
        request_source="support",
        request_reason="Refund already created",
        status=REFUND_STATUS_PROVIDER_FOLLOWUP_REQUIRED,
        auto_decision=False,
        eligibility_snapshot_json={},
        usage_snapshot_json={},
        provider_response_json={"adjustment_create": {"id": "adj_deny_followup_123"}},
        requested_by_admin_user_id=admin_user.id,
    )
    db.add_all([pending_provider_review, followup_review])
    await db.commit()

    pending_response = await client.post(
        f"/api/v1/admin/refunds/reviews/{pending_provider_review.id}/deny",
        json={"reason": "Should not be allowed"},
        headers=admin_headers,
    )
    followup_response = await client.post(
        f"/api/v1/admin/refunds/reviews/{followup_review.id}/deny",
        json={"reason": "Should not be allowed"},
        headers=admin_headers,
    )

    assert pending_response.status_code == 409
    assert "submitted to the provider" in pending_response.json()["detail"]
    assert followup_response.status_code == 409
    assert "provider refund in flight" in followup_response.json()["detail"]


# ── Admin CSRF bearer validation tests ──────────────────────────────────


@pytest.mark.asyncio
async def test_admin_csrf_allows_valid_bearer_access_token(client, db):
    headers, user_id = await _register_user(client, f"admin-csrf-bearer-valid-{uuid.uuid4().hex[:8]}@lorevia.app")
    await _grant_admin(client, db, user_id, headers)

    response = await client.get("/api/v1/admin/session", headers=headers)
    assert response.status_code == 200
    assert response.json()["is_admin"] is True


@pytest.mark.asyncio
async def test_admin_csrf_falls_back_to_cookie_when_bearer_is_invalid(client, db):
    from app.utils.admin_security import ADMIN_CSRF_COOKIE_NAME, ADMIN_CSRF_HEADER_NAME

    headers, user_id = await _register_user(client, f"admin-csrf-cookie-fallback-{uuid.uuid4().hex[:8]}@lorevia.app")
    await _grant_admin(client, db, user_id, headers)

    session_response = await client.get("/api/v1/admin/session", headers=headers)
    csrf_token: str | None = None
    for raw in session_response.headers.get_list("set-cookie"):
        if ADMIN_CSRF_COOKIE_NAME in raw:
            csrf_token = raw.split(";")[0].split("=", 1)[1] if "=" in raw else None
    assert csrf_token is not None

    existing_cookie = headers.get("Cookie", "")
    invalid_bearer = "Bearer invalid-token-not-a-jwt"
    headers["Authorization"] = invalid_bearer
    headers["Cookie"] = f"{existing_cookie}; {ADMIN_CSRF_COOKIE_NAME}={csrf_token}"
    headers[ADMIN_CSRF_HEADER_NAME] = csrf_token
    headers["Origin"] = "https://getlorevia.com"

    response = await client.post(
        "/api/v1/admin/step-up",
        json={"password": "WrongPassword123!@#"},
        headers=headers,
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid admin verification."


@pytest.mark.asyncio
async def test_admin_csrf_rejects_missing_bearer_and_csrf_header(client, db):
    headers, user_id = await _register_user(client, f"admin-csrf-reject-{uuid.uuid4().hex[:8]}@lorevia.app")
    await _grant_admin(client, db, user_id, headers)

    del headers["Authorization"]

    if "Cookie" in headers:
        del headers["Cookie"]

    headers["Origin"] = "https://getlorevia.com"

    response = await client.post(
        "/api/v1/admin/step-up",
        json={"password": "StrongPass123!@#"},
        headers=headers,
    )

    assert response.status_code == 403
    assert "Invalid admin CSRF token" in response.json()["detail"]


@pytest.mark.asyncio
async def test_admin_can_hide_remove_and_restore_public_book(client, db):
    headers, admin_id = await _register_user(
        client,
        f"admin-moderation-{uuid.uuid4().hex[:8]}@lorevia.app",
    )
    await _grant_admin(client, db, admin_id, headers, scopes=["moderation_admin"])
    _owner_headers, owner_id = await _register_user(
        client,
        f"moderated-owner-{uuid.uuid4().hex[:8]}@lorevia.app",
    )
    book = Book(
        user_id=owner_id,
        title="Moderated Novel",
        format="txt",
        s3_key="public/moderated.txt",
        status="ready",
        is_public=True,
        public_status="published",
        moderation_status="clean",
    )
    db.add(book)
    await db.commit()

    hidden = await client.post(
        f"/api/v1/admin/books/{book.id}/hide",
        headers=headers,
        json={"reason": "Pending moderation review."},
    )
    assert hidden.status_code == 200, hidden.text
    assert hidden.json()["moderation_status"] == "hidden"

    removed = await client.post(
        f"/api/v1/admin/books/{book.id}/remove",
        headers=headers,
        json={"reason": "Confirmed policy violation."},
    )
    assert removed.status_code == 200
    assert removed.json()["moderation_status"] == "removed"

    restored = await client.post(
        f"/api/v1/admin/books/{book.id}/restore",
        headers=headers,
        json={"reason": "Appeal accepted."},
    )
    assert restored.status_code == 200
    assert restored.json()["moderation_status"] == "clean"
    await db.refresh(book)
    assert book.is_public is True
    assert book.takedown_reason is None


@pytest.mark.asyncio
async def test_owner_admin_manages_access_rate_limits_tiers_and_audit(client, db):
    headers, owner_id = await _register_user(
        client,
        f"admin-owner-{uuid.uuid4().hex[:8]}@lorevia.app",
    )
    await _grant_admin(client, db, owner_id, headers)
    _target_headers, target_id = await _register_user(
        client,
        f"admin-target-{uuid.uuid4().hex[:8]}@lorevia.app",
    )

    granted = await client.post(
        "/api/v1/admin/access",
        headers=headers,
        json={
            "user_id": str(target_id),
            "scopes": ["billing_admin"],
            "is_owner": False,
            "reason": "Billing support rotation.",
        },
    )
    assert granted.status_code == 200, granted.text
    principal_id = granted.json()["id"]

    access = await client.get("/api/v1/admin/access", headers=headers)
    assert access.status_code == 200
    assert any(item["id"] == principal_id for item in access.json())

    rate_update = await client.put(
        f"/api/v1/admin/rate-limits/{target_id}",
        headers=headers,
        json={
            "search_per_hour": 50,
            "summary_per_hour": 20,
            "chat_per_day": 100,
            "api_per_minute": 120,
        },
    )
    assert rate_update.status_code == 200, rate_update.text
    rate_read = await client.get(f"/api/v1/admin/rate-limits/{target_id}", headers=headers)
    assert rate_read.status_code == 200
    assert rate_read.json()["override"]["search_per_hour"] == 50

    tier = await client.put(
        f"/api/v1/admin/users/{target_id}/tier",
        headers=headers,
        json={"tier": "architect"},
    )
    assert tier.status_code == 200
    assert tier.json()["tier"] == "architect"

    audit = await client.get("/api/v1/admin/audit", headers=headers)
    assert audit.status_code == 200
    assert any(item["action_type"] == "admin_access_granted" for item in audit.json())

    revoked = await client.post(
        f"/api/v1/admin/access/{principal_id}/revoke",
        headers=headers,
        json={"reason": "Rotation completed."},
    )
    assert revoked.status_code == 200
    assert revoked.json()["status"] == "revoked"
