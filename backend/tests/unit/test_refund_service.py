import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.models.book import Book
from app.models.user import RefundReview, Subscription, User
from app.services.refund_service import (
    ADJUSTMENT_CREATE_ERROR_MESSAGE,
    AUTO_REFUND_SUBSCRIPTION_LINKAGE_ERROR_MESSAGE,
    CANCEL_SUBSCRIPTION_ERROR_MESSAGE,
    REFUND_STATUS_APPROVED,
    REFUND_STATUS_APPROVED_PENDING_PROVIDER,
    REFUND_STATUS_MANUAL_REVIEW_REQUIRED,
    REFUND_STATUS_PROVIDER_FOLLOWUP_REQUIRED,
    create_refund_review_request,
    evaluate_refund_eligibility,
)


async def _create_user(db, *, email_prefix: str = "refund") -> User:
    user = User(
        email=f"{email_prefix}-{uuid.uuid4().hex[:8]}@lorevia.app",
        username=f"{email_prefix}{uuid.uuid4().hex[:8]}",
        password_hash="hash",
        created_at=datetime.now(UTC) - timedelta(days=10),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


def _transaction_summary(*, user: User, charge_at: datetime, billing_interval: str = "monthly"):
    return SimpleNamespace(
        transaction_id="txn_123",
        status="completed",
        plan=f"author_{billing_interval}",
        billing_interval=billing_interval,
        display_name="Author",
        currency_code="USD",
        total="USD 19.00",
        invoice_number="INV-123",
        invoice_pdf_url="https://files.paddle.com/invoice.pdf",
        subscription_id="sub_123",
        customer_email=user.email,
        customer_id="ctm_123",
        charge_at=charge_at,
    )


@pytest.mark.asyncio
async def test_evaluate_refund_eligibility_auto_approves_monthly_charge_with_no_usage(db):
    user = await _create_user(db, email_prefix="refund-auto")
    now = datetime.now(UTC)

    result = await evaluate_refund_eligibility(
        db,
        user_id=user.id,
        transaction_id="txn_auto",
        billing_interval="monthly",
        charge_at=now - timedelta(hours=1),
        transaction_status="completed",
        now=now,
    )

    assert result.auto_approve is True
    assert result.usage_snapshot["has_meaningful_usage"] is False


@pytest.mark.asyncio
async def test_evaluate_refund_eligibility_requires_manual_review_for_annual_charge(db):
    user = await _create_user(db, email_prefix="refund-annual")
    now = datetime.now(UTC)

    result = await evaluate_refund_eligibility(
        db,
        user_id=user.id,
        transaction_id="txn_annual",
        billing_interval="annual",
        charge_at=now - timedelta(hours=1),
        transaction_status="completed",
        now=now,
    )

    assert result.auto_approve is False
    assert "Annual charges" in result.decision_reason


@pytest.mark.asyncio
async def test_evaluate_refund_eligibility_requires_manual_review_when_post_charge_usage_exists(db):
    user = await _create_user(db, email_prefix="refund-usage")
    now = datetime.now(UTC)
    charge_at = now - timedelta(hours=2)
    db.add(
        Book(
            user_id=user.id,
            title="Post-charge project",
            format="txt",
            s3_key="books/post-charge.txt",
            status="ready",
            created_at=charge_at + timedelta(minutes=30),
        )
    )
    await db.commit()

    result = await evaluate_refund_eligibility(
        db,
        user_id=user.id,
        transaction_id="txn_usage",
        billing_interval="monthly",
        charge_at=charge_at,
        transaction_status="completed",
        now=now,
    )

    assert result.auto_approve is False
    assert result.usage_snapshot["book_count"] == 1
    assert result.usage_snapshot["has_meaningful_usage"] is True


@pytest.mark.asyncio
async def test_evaluate_refund_eligibility_requires_manual_review_outside_24_hour_window(db):
    user = await _create_user(db, email_prefix="refund-window")
    now = datetime.now(UTC)

    result = await evaluate_refund_eligibility(
        db,
        user_id=user.id,
        transaction_id="txn_window",
        billing_interval="monthly",
        charge_at=now - timedelta(hours=25),
        transaction_status="completed",
        now=now,
    )

    assert result.auto_approve is False
    assert "24-hour" in result.decision_reason


@pytest.mark.asyncio
async def test_evaluate_refund_eligibility_requires_manual_review_for_new_account(db):
    user = User(
        email=f"refund-new-account-{uuid.uuid4().hex[:8]}@lorevia.app",
        username=f"refundnewacct{uuid.uuid4().hex[:8]}",
        password_hash="hash",
        created_at=datetime.now(UTC) - timedelta(hours=12),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    now = datetime.now(UTC)

    result = await evaluate_refund_eligibility(
        db,
        user_id=user.id,
        transaction_id="txn_new_account",
        billing_interval="monthly",
        charge_at=now - timedelta(hours=1),
        transaction_status="completed",
        now=now,
    )

    assert result.auto_approve is False
    assert "too new" in result.decision_reason
    assert result.eligibility_snapshot["meets_account_age_requirement"] is False


@pytest.mark.asyncio
async def test_evaluate_refund_eligibility_requires_manual_review_after_two_approved_refunds(db):
    user = await _create_user(db, email_prefix="refund-history")
    now = datetime.now(UTC)

    db.add_all(
        [
            RefundReview(
                user_id=user.id,
                paddle_transaction_id=f"txn_history_{index}",
                charge_at=now - timedelta(days=index + 1),
                plan_code="author_monthly",
                billing_interval="monthly",
                request_source="support",
                request_reason="Prior refund",
                status=REFUND_STATUS_APPROVED,
                eligibility_snapshot_json={},
                usage_snapshot_json={},
                provider_response_json={},
            )
            for index in range(2)
        ]
    )
    await db.commit()

    result = await evaluate_refund_eligibility(
        db,
        user_id=user.id,
        transaction_id="txn_history_new",
        billing_interval="monthly",
        charge_at=now - timedelta(hours=3),
        transaction_status="completed",
        now=now,
    )

    assert result.auto_approve is False
    assert result.eligibility_snapshot["approved_refund_count"] == 2


@pytest.mark.asyncio
async def test_evaluate_refund_eligibility_counts_submitted_refunds_pending_provider_follow_up(db):
    user = await _create_user(db, email_prefix="refund-submitted-history")
    now = datetime.now(UTC)

    db.add_all(
        [
            RefundReview(
                user_id=user.id,
                paddle_transaction_id="txn_submitted_1",
                paddle_adjustment_id="adj_submitted_1",
                charge_at=now - timedelta(days=2),
                plan_code="author_monthly",
                billing_interval="monthly",
                request_source="support",
                request_reason="Prior submitted refund",
                status=REFUND_STATUS_PROVIDER_FOLLOWUP_REQUIRED,
                eligibility_snapshot_json={},
                usage_snapshot_json={},
                provider_response_json={"adjustment_create": {"id": "adj_submitted_1"}},
            ),
            RefundReview(
                user_id=user.id,
                paddle_transaction_id="txn_submitted_2",
                paddle_adjustment_id="adj_submitted_2",
                charge_at=now - timedelta(days=1),
                plan_code="author_monthly",
                billing_interval="monthly",
                request_source="support",
                request_reason="Prior pending provider refund",
                status=REFUND_STATUS_APPROVED_PENDING_PROVIDER,
                eligibility_snapshot_json={},
                usage_snapshot_json={},
                provider_response_json={"adjustment_create": {"id": "adj_submitted_2"}},
            ),
        ]
    )
    await db.commit()

    result = await evaluate_refund_eligibility(
        db,
        user_id=user.id,
        transaction_id="txn_submitted_new",
        billing_interval="monthly",
        charge_at=now - timedelta(hours=2),
        transaction_status="completed",
        now=now,
    )

    assert result.auto_approve is False
    assert result.eligibility_snapshot["approved_refund_count"] == 2


@pytest.mark.asyncio
async def test_create_refund_review_request_is_idempotent_for_duplicate_active_transaction(
    db, monkeypatch
):
    user = await _create_user(db, email_prefix="refund-duplicate")
    subscription = Subscription(
        user_id=user.id,
        plan="author_monthly",
        status="active",
        paddle_sub_id="sub_123",
        paddle_transaction_id="txn_123",
    )
    db.add(subscription)
    await db.commit()
    await db.refresh(subscription)

    now = datetime.now(UTC)

    async def fake_get_transaction_summary(transaction_id: str):
        assert transaction_id == "txn_123"
        return _transaction_summary(user=user, charge_at=now - timedelta(hours=1))

    async def fake_create_refund_adjustment(transaction_id: str, reason: str):
        assert transaction_id == "txn_123"
        assert reason == "Duplicate-safe refund request"
        return {"id": "adj_123", "status": "pending_approval"}

    async def fake_cancel_subscription_immediately(subscription_id: str):
        assert subscription_id == "sub_123"
        return {"id": "sub_123", "status": "canceled"}

    monkeypatch.setattr(
        "app.services.refund_service.get_transaction_summary", fake_get_transaction_summary
    )
    monkeypatch.setattr(
        "app.services.refund_service.create_refund_adjustment", fake_create_refund_adjustment
    )
    monkeypatch.setattr(
        "app.services.refund_service.cancel_subscription_immediately",
        fake_cancel_subscription_immediately,
    )

    first_review = await create_refund_review_request(
        db,
        transaction_id="txn_123",
        request_reason="Duplicate-safe refund request",
        request_source="support",
        support_reference="CASE-1",
        requested_by_admin_user_id=user.id,
        now=now,
    )
    second_review = await create_refund_review_request(
        db,
        transaction_id="txn_123",
        request_reason="Duplicate-safe refund request",
        request_source="support",
        support_reference="CASE-2",
        requested_by_admin_user_id=user.id,
        now=now,
    )

    review_count = int(
        (
            await db.execute(
                select(func.count(RefundReview.id)).where(
                    RefundReview.paddle_transaction_id == "txn_123"
                )
            )
        ).scalar()
        or 0
    )

    assert first_review.id == second_review.id
    assert review_count == 1


@pytest.mark.asyncio
async def test_create_refund_review_request_recovers_when_duplicate_insert_conflicts_on_flush(
    db, monkeypatch
):
    user = await _create_user(db, email_prefix="refund-duplicate-flush")
    existing_review = RefundReview(
        user_id=user.id,
        paddle_transaction_id="txn_flush_conflict",
        charge_at=datetime.now(UTC) - timedelta(hours=1),
        plan_code="author_monthly",
        billing_interval="monthly",
        request_source="support",
        request_reason="Existing in-flight refund",
        status=REFUND_STATUS_MANUAL_REVIEW_REQUIRED,
        auto_decision=False,
        decision_reason="Existing manual review",
        eligibility_snapshot_json={},
        usage_snapshot_json={},
        provider_response_json={},
        requested_by_admin_user_id=user.id,
    )
    db.add(existing_review)
    await db.commit()
    await db.refresh(existing_review)
    existing_review_id = existing_review.id

    async def fake_get_transaction_summary(transaction_id: str):
        assert transaction_id == "txn_flush_conflict"
        return _transaction_summary(user=user, charge_at=datetime.now(UTC) - timedelta(hours=1))

    find_active_calls = 0

    async def fake_find_active_review_for_transaction(_db, transaction_id: str):
        nonlocal find_active_calls
        assert transaction_id == "txn_flush_conflict"
        find_active_calls += 1
        if find_active_calls == 1:
            return None
        return SimpleNamespace(id=existing_review_id)

    original_flush = db.flush

    async def fake_flush(*args, **kwargs):
        raise IntegrityError(
            "duplicate key value violates unique constraint", params=None, orig=None
        )

    monkeypatch.setattr(
        "app.services.refund_service.get_transaction_summary", fake_get_transaction_summary
    )
    monkeypatch.setattr(
        "app.services.refund_service._find_active_review_for_transaction",
        fake_find_active_review_for_transaction,
    )

    async def fake_find_latest_review_for_transaction(*_args, **_kwargs):
        return None

    monkeypatch.setattr(
        "app.services.refund_service._find_latest_review_for_transaction",
        fake_find_latest_review_for_transaction,
    )
    monkeypatch.setattr(db, "flush", fake_flush)

    result = await create_refund_review_request(
        db,
        transaction_id="txn_flush_conflict",
        request_reason="Concurrent refund request",
        request_source="support",
        support_reference="CASE-FLUSH",
        requested_by_admin_user_id=user.id,
        now=datetime.now(UTC),
    )

    monkeypatch.setattr(db, "flush", original_flush)

    assert result.id == existing_review_id
    assert find_active_calls == 2


@pytest.mark.asyncio
async def test_create_refund_review_request_sanitizes_provider_exception_details(db, monkeypatch):
    user = await _create_user(db, email_prefix="refund-provider-error")
    subscription = Subscription(
        user_id=user.id,
        plan="author_monthly",
        status="active",
        paddle_sub_id="sub_provider_error_123",
        paddle_transaction_id="txn_provider_error_123",
    )
    db.add(subscription)
    await db.commit()

    now = datetime.now(UTC)

    async def fake_get_transaction_summary(transaction_id: str):
        assert transaction_id == "txn_provider_error_123"
        return _transaction_summary(user=user, charge_at=now - timedelta(hours=1))

    async def fake_create_refund_adjustment(transaction_id: str, reason: str):
        raise httpx.HTTPError(
            "authorization=Bearer provider-secret-token "
            "database_url=postgresql://refund_user:refund_pass@db.example.com/refunds"
        )

    monkeypatch.setattr(
        "app.services.refund_service.get_transaction_summary", fake_get_transaction_summary
    )
    monkeypatch.setattr(
        "app.services.refund_service.create_refund_adjustment", fake_create_refund_adjustment
    )

    review = await create_refund_review_request(
        db,
        transaction_id="txn_provider_error_123",
        request_reason="Need refund",
        request_source="support",
        support_reference="CASE-PROVIDER-ERROR",
        requested_by_admin_user_id=user.id,
        now=now,
    )

    assert review.status == REFUND_STATUS_PROVIDER_FOLLOWUP_REQUIRED
    assert (
        review.provider_response_json["adjustment_create_error"] == ADJUSTMENT_CREATE_ERROR_MESSAGE
    )
    assert (
        "provider-secret-token"
        not in review.provider_response_json["adjustment_create_error_redacted"]
    )
    assert "refund_pass" not in review.provider_response_json["adjustment_create_error_redacted"]
    assert "[REDACTED]" in review.provider_response_json["adjustment_create_error_redacted"]


@pytest.mark.asyncio
async def test_create_refund_review_request_sanitizes_subscription_cancellation_exception_details(
    db, monkeypatch
):
    user = await _create_user(db, email_prefix="refund-cancel-error")
    subscription = Subscription(
        user_id=user.id,
        plan="author_monthly",
        status="active",
        paddle_sub_id="sub_cancel_error_123",
        paddle_transaction_id="txn_cancel_error_123",
    )
    db.add(subscription)
    await db.commit()

    now = datetime.now(UTC)

    async def fake_get_transaction_summary(transaction_id: str):
        assert transaction_id == "txn_cancel_error_123"
        return _transaction_summary(user=user, charge_at=now - timedelta(hours=1))

    async def fake_create_refund_adjustment(transaction_id: str, reason: str):
        return {"id": "adj_cancel_error_123", "status": "pending_approval"}

    async def fake_cancel_subscription_immediately(subscription_id: str):
        raise httpx.HTTPError(
            "x-api-key=provider-key-123 cookie=session_cookie "
            "database_url=postgresql://cancel_user:cancel_pass@db.example.com/refunds"
        )

    monkeypatch.setattr(
        "app.services.refund_service.get_transaction_summary", fake_get_transaction_summary
    )
    monkeypatch.setattr(
        "app.services.refund_service.create_refund_adjustment", fake_create_refund_adjustment
    )
    monkeypatch.setattr(
        "app.services.refund_service.cancel_subscription_immediately",
        fake_cancel_subscription_immediately,
    )

    review = await create_refund_review_request(
        db,
        transaction_id="txn_cancel_error_123",
        request_reason="Need refund",
        request_source="support",
        support_reference="CASE-CANCEL-ERROR",
        requested_by_admin_user_id=user.id,
        now=now,
    )

    assert review.status == REFUND_STATUS_PROVIDER_FOLLOWUP_REQUIRED
    assert (
        review.provider_response_json["cancel_subscription_error"]
        == CANCEL_SUBSCRIPTION_ERROR_MESSAGE
    )
    assert (
        "provider-key-123"
        not in review.provider_response_json["cancel_subscription_error_redacted"]
    )
    assert "cancel_pass" not in review.provider_response_json["cancel_subscription_error_redacted"]
    assert "[REDACTED]" in review.provider_response_json["cancel_subscription_error_redacted"]


@pytest.mark.asyncio
async def test_create_refund_review_request_propagates_unexpected_provider_client_bug(
    db, monkeypatch
):
    user = await _create_user(db, email_prefix="refund-provider-bug")
    subscription = Subscription(
        user_id=user.id,
        plan="author_monthly",
        status="active",
        paddle_sub_id="sub_provider_bug_123",
        paddle_transaction_id="txn_provider_bug_123",
    )
    db.add(subscription)
    await db.commit()

    now = datetime.now(UTC)

    async def fake_get_transaction_summary(transaction_id: str):
        assert transaction_id == "txn_provider_bug_123"
        return SimpleNamespace(
            transaction_id="txn_provider_bug_123",
            status="completed",
            plan="author_monthly",
            billing_interval="monthly",
            display_name="Author",
            currency_code="USD",
            total="USD 19.00",
            invoice_number="INV-123",
            invoice_pdf_url="https://files.paddle.com/invoice.pdf",
            subscription_id="sub_provider_bug_123",
            customer_email=user.email,
            customer_id="ctm_123",
            charge_at=now - timedelta(hours=1),
        )

    async def fake_create_refund_adjustment(transaction_id: str, reason: str):
        raise RuntimeError("provider client regression")

    monkeypatch.setattr(
        "app.services.refund_service.get_transaction_summary", fake_get_transaction_summary
    )
    monkeypatch.setattr(
        "app.services.refund_service.create_refund_adjustment", fake_create_refund_adjustment
    )

    with pytest.raises(RuntimeError, match="provider client regression"):
        await create_refund_review_request(
            db,
            transaction_id="txn_provider_bug_123",
            request_reason="Need refund",
            request_source="support",
            support_reference="CASE-PROVIDER-BUG",
            requested_by_admin_user_id=user.id,
            now=now,
        )


@pytest.mark.asyncio
async def test_create_refund_review_request_requires_manual_review_when_monthly_subscription_linkage_is_missing(
    db, monkeypatch
):
    user = await _create_user(db, email_prefix="refund-no-sub-link")
    now = datetime.now(UTC)

    async def fake_get_transaction_summary(transaction_id: str):
        assert transaction_id == "txn_no_sub_link_123"
        return SimpleNamespace(
            transaction_id="txn_no_sub_link_123",
            status="completed",
            plan="author_monthly",
            billing_interval="monthly",
            display_name="Author",
            currency_code="USD",
            total="USD 19.00",
            invoice_number="INV-123",
            invoice_pdf_url="https://files.paddle.com/invoice.pdf",
            subscription_id="sub_missing_local_link",
            customer_email=user.email,
            customer_id="ctm_123",
            charge_at=now - timedelta(hours=1),
        )

    async def fail_create_refund_adjustment(transaction_id: str, reason: str):
        raise AssertionError(
            "Provider refund creation should not run without safe subscription linkage"
        )

    monkeypatch.setattr(
        "app.services.refund_service.get_transaction_summary", fake_get_transaction_summary
    )
    monkeypatch.setattr(
        "app.services.refund_service.create_refund_adjustment", fail_create_refund_adjustment
    )

    review = await create_refund_review_request(
        db,
        transaction_id="txn_no_sub_link_123",
        request_reason="Monthly refund without safe subscription linkage",
        request_source="support",
        support_reference="CASE-NO-SUB-LINK",
        requested_by_admin_user_id=user.id,
        now=now,
    )

    assert review.status == "manual_review_required"
    assert review.auto_decision is False
    assert review.decision_reason == AUTO_REFUND_SUBSCRIPTION_LINKAGE_ERROR_MESSAGE
    assert review.eligibility_snapshot_json["has_required_subscription_linkage"] is False
