import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.models.book import Book, BookUploadCharge, Series, SeriesBook
from app.models.intelligence import WorldBuildingDocument
from app.models.user import SubscriptionEvent, User
from app.utils.billing_utils import (
    append_billing_confirmation_token,
    build_subscription_metrics_summary,
    calculate_upload_usage_summary,
    consume_billing_confirmation_token_once,
    create_billing_confirmation_token,
    ensure_upload_capacity,
    normalize_tier,
    paddle_plan_from_event_data,
    recommended_paddle_default_checkout_url,
    record_book_upload_charge,
    summary_mode_allowed,
    verify_billing_confirmation_token,
    worldbuilding_upload_cost_for_book,
)


@pytest.mark.asyncio
async def test_worldbuilding_upload_cost_scales_with_series_book_count(db):
    user = User(email="billing-series@lorevia.app", username="billingseries", password_hash="hash", tier="author")
    db.add(user)
    await db.flush()

    series = Series(user_id=user.id, name="Atlas Cycle")
    db.add(series)
    await db.flush()

    books = [
        Book(user_id=user.id, title="Book One", format="txt", s3_key="books/one.txt", status="ready", primary_series_id=series.id),
        Book(user_id=user.id, title="Book Two", format="txt", s3_key="books/two.txt", status="ready", primary_series_id=series.id),
        Book(user_id=user.id, title="Book Three", format="txt", s3_key="books/three.txt", status="ready", primary_series_id=series.id),
    ]
    db.add_all(books)
    await db.flush()
    db.add_all([SeriesBook(series_id=series.id, book_id=book.id) for book in books])
    await db.commit()

    assert await worldbuilding_upload_cost_for_book(db, books[0]) == 3


@pytest.mark.asyncio
async def test_calculate_upload_usage_counts_weighted_worldbuilding_documents(db):
    user = User(email="billing-usage@lorevia.app", username="billingusage", password_hash="hash", tier="author")
    db.add(user)
    await db.flush()

    series = Series(user_id=user.id, name="Northreach")
    db.add(series)
    await db.flush()

    series_books = [
        Book(user_id=user.id, title="Volume I", format="txt", s3_key="books/i.txt", status="ready", primary_series_id=series.id),
        Book(user_id=user.id, title="Volume II", format="txt", s3_key="books/ii.txt", status="ready", primary_series_id=series.id),
    ]
    solo_book = Book(user_id=user.id, title="Standalone", format="txt", s3_key="books/solo.txt", status="ready")
    db.add_all([*series_books, solo_book])
    await db.flush()
    db.add_all([SeriesBook(series_id=series.id, book_id=book.id) for book in series_books])
    db.add_all(
        [
            WorldBuildingDocument(book_id=series_books[0].id, title="Series Bible", s3_key="world/series.json", is_active=True),
            WorldBuildingDocument(book_id=solo_book.id, title="Solo Notes", s3_key="world/solo.json", is_active=True),
        ]
    )
    await db.commit()

    usage = await calculate_upload_usage_summary(db, user)

    assert usage.manuscript_uploads == 3
    assert usage.worldbuilding_uploads == 3
    assert usage.total_uploads == 6
    assert usage.upload_limit == 15
    assert usage.uploads_remaining == 9


@pytest.mark.asyncio
async def test_calculate_upload_usage_includes_manual_reprocess_charges(db):
    user = User(email="billing-reprocess@lorevia.app", username="billingreprocess", password_hash="hash", tier="author")
    db.add(user)
    await db.flush()
    book = Book(user_id=user.id, title="Charged Project", format="txt", s3_key="books/charged.txt", status="ready")
    db.add(book)
    await db.flush()
    db.add(
        BookUploadCharge(
            user_id=user.id,
            book_id=book.id,
            charge_kind="manual_reprocess",
            quantity=1,
            source_id="run-1",
        )
    )
    await db.commit()

    usage = await calculate_upload_usage_summary(db, user)

    assert usage.manuscript_uploads == 2
    assert usage.total_uploads == 2
    assert usage.uploads_remaining == 13


@pytest.mark.asyncio
async def test_record_book_upload_charge_is_idempotent_by_source(db):
    user = User(email="billing-charge-idem@lorevia.app", username="billingchargeidem", password_hash="hash", tier="author")
    db.add(user)
    await db.flush()
    book = Book(user_id=user.id, title="Idempotent Project", format="txt", s3_key="books/idempotent.txt", status="ready")
    db.add(book)
    await db.flush()

    first = await record_book_upload_charge(
        db,
        user_id=user.id,
        book_id=book.id,
        charge_kind="manual_reprocess",
        source_id="run-idem",
    )
    second = await record_book_upload_charge(
        db,
        user_id=user.id,
        book_id=book.id,
        charge_kind="manual_reprocess",
        source_id="run-idem",
    )
    await db.commit()

    count = await db.scalar(select(func.count()).select_from(BookUploadCharge).where(BookUploadCharge.user_id == user.id))
    assert first.id == second.id
    assert count == 1


@pytest.mark.asyncio
async def test_record_book_upload_charge_uses_savepoint_for_idempotency_race():
    existing = BookUploadCharge(
        user_id=uuid.uuid4(),
        book_id=uuid.uuid4(),
        charge_kind="manual_reprocess",
        source_id="run-race",
    )

    class _ScalarResult:
        def __init__(self, value):
            self.value = value

        def scalar_one_or_none(self):
            return self.value

    class _NestedTransaction:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

    db = MagicMock()
    db.execute = AsyncMock(side_effect=[_ScalarResult(None), _ScalarResult(existing)])
    db.flush = AsyncMock(side_effect=IntegrityError("duplicate", {}, Exception("duplicate")))
    db.rollback = AsyncMock()
    db.begin_nested.return_value = _NestedTransaction()

    result = await record_book_upload_charge(
        db,
        user_id=existing.user_id,
        book_id=existing.book_id,
        charge_kind="manual_reprocess",
        source_id="run-race",
    )

    assert result is existing
    db.begin_nested.assert_called_once_with()
    db.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_ensure_upload_capacity_blocks_author_when_series_weight_pushes_past_cap(db):
    user = User(email="billing-cap@lorevia.app", username="billingcap", password_hash="hash", tier="author")
    db.add(user)
    await db.flush()

    books = [
        Book(user_id=user.id, title=f"Project {index}", format="txt", s3_key=f"books/{index}.txt", status="ready")
        for index in range(1, 15)
    ]
    db.add_all(books)
    await db.commit()

    with pytest.raises(HTTPException) as exc:
        await ensure_upload_capacity(
            db,
            user,
            requested_uploads=2,
            context="This worldbuilding upload counts as 2 uploads for this book.",
        )

    assert exc.value.status_code == 403
    assert "Author tier includes 15 uploads" in exc.value.detail
    assert "counts as 2 uploads" in exc.value.detail


@pytest.mark.asyncio
async def test_ensure_upload_capacity_blocks_free_users_from_new_uploads(db):
    user = User(
        email="billing-free-cap@lorevia.app",
        username="billingfreecap",
        password_hash="hash",
        tier="free",
        created_at=datetime.now(UTC) - timedelta(days=20),
    )
    db.add(user)
    await db.flush()

    db.add(Book(user_id=user.id, title="Only Project", format="txt", s3_key="books/free.txt", status="ready"))
    await db.commit()

    with pytest.raises(HTTPException) as exc:
        await ensure_upload_capacity(db, user, requested_uploads=1)

    assert exc.value.status_code == 403
    assert "This account is limited to 0 owned uploads" in exc.value.detail


@pytest.mark.asyncio
async def test_ensure_upload_capacity_treats_legacy_reader_alias_like_non_author_owner_for_uploads(db):
    user = User(
        email="billing-reader-cap@lorevia.app",
        username="billingreadercap",
        password_hash="hash",
        tier="reader",
        created_at=datetime.now(UTC) - timedelta(days=20),
    )
    db.add(user)
    await db.flush()

    db.add(Book(user_id=user.id, title="Reader Project", format="txt", s3_key="books/reader.txt", status="ready"))
    await db.commit()

    with pytest.raises(HTTPException) as exc:
        await ensure_upload_capacity(db, user, requested_uploads=1)

    assert exc.value.status_code == 403
    assert "Upgrade to Author for higher owner upload limits." in exc.value.detail


def test_paddle_plan_from_event_data_does_not_default_unknown_events_to_reader():
    assert paddle_plan_from_event_data({"items": []}) == ""


def test_paddle_plan_from_event_data_maps_legacy_pro_labels_to_author_plan():
    payload = {
        "items": [
            {
                "price": {
                    "name": "LoreVia Pro",
                    "billing_cycle": {"interval": "month"},
                }
            }
        ]
    }

    assert paddle_plan_from_event_data(payload) == "author_monthly"


def test_recommended_paddle_default_checkout_url_uses_app_url(monkeypatch):
    monkeypatch.setattr("app.utils.billing_utils.settings.APP_URL", "https://app.getlorevia.com", raising=False)

    assert recommended_paddle_default_checkout_url() == "https://app.getlorevia.com/checkout"


def test_billing_confirmation_token_round_trip(monkeypatch):
    monkeypatch.setattr("app.utils.billing_utils.settings.JWT_SECRET", "jwt-secret", raising=False)
    monkeypatch.setattr("app.utils.billing_utils.settings.JWT_ALGORITHM", "HS256", raising=False)

    token = create_billing_confirmation_token("txn_123")

    assert verify_billing_confirmation_token(token, "txn_123") is True
    assert verify_billing_confirmation_token(token, "txn_other") is False


@pytest.mark.asyncio
async def test_billing_confirmation_token_can_only_be_consumed_once(monkeypatch):
    consumed_token_ids: set[str] = set()

    async def _consume(token_id: str, ttl_seconds: int) -> bool:
        assert ttl_seconds > 0
        if token_id in consumed_token_ids:
            return False
        consumed_token_ids.add(token_id)
        return True

    monkeypatch.setattr("app.utils.billing_utils.settings.JWT_SECRET", "jwt-secret", raising=False)
    monkeypatch.setattr("app.utils.billing_utils.settings.JWT_ALGORITHM", "HS256", raising=False)
    monkeypatch.setattr("app.utils.billing_utils.consume_billing_confirmation_token", _consume)
    token = create_billing_confirmation_token("txn_123")

    assert await consume_billing_confirmation_token_once(token, "txn_123") is True
    assert await consume_billing_confirmation_token_once(token, "txn_123") is False


def test_append_billing_confirmation_token_preserves_existing_checkout_query():
    updated = append_billing_confirmation_token(
        "https://getlorevia.com/checkout?_ptxn=txn_123",
        "token_123",
    )

    assert updated == "https://getlorevia.com/checkout?_ptxn=txn_123&lvct=token_123"


def test_normalize_tier_maps_legacy_reader_aliases_back_to_free():
    assert normalize_tier("collaborator") == "free"
    assert normalize_tier("reader") == "free"


def test_summary_modes_allow_short_for_all_tiers_but_restrict_post_trial_free_users():
    expired_free_user = User(
        email="free@lorevia.app",
        username="freeuser",
        password_hash="hash",
        tier="free",
        created_at=datetime.now(UTC) - timedelta(days=20),
    )
    active_trial_user = User(
        email="trial@lorevia.app",
        username="trialuser",
        password_hash="hash",
        tier="free",
        created_at=datetime.now(UTC),
    )
    legacy_reader_user = User(
        email="reader@lorevia.app",
        username="readeruser",
        password_hash="hash",
        tier="reader",
        created_at=datetime.now(UTC) - timedelta(days=20),
    )
    paid_user = User(
        email="author@lorevia.app",
        username="authoruser",
        password_hash="hash",
        tier="author",
        created_at=datetime.now(UTC) - timedelta(days=20),
    )

    assert summary_mode_allowed(expired_free_user, "short") is True
    assert summary_mode_allowed(expired_free_user, "detailed") is False
    assert summary_mode_allowed(expired_free_user, "key_points") is False

    for user in (active_trial_user, legacy_reader_user, paid_user):
        assert summary_mode_allowed(user, "short") is True
        assert summary_mode_allowed(user, "detailed") is True
        assert summary_mode_allowed(user, "key_points") is True


@pytest.mark.asyncio
async def test_build_subscription_metrics_summary_reports_trial_conversion_and_post_cancel_churn(db):
    now = datetime(2030, 6, 20, 12, 0, tzinfo=UTC)
    cohort_start = datetime(2030, 5, 1, 8, 0, tzinfo=UTC)

    converted_user = User(
        email="metrics-converted@lorevia.app",
        username="metricsconverted",
        password_hash="hash",
        created_at=cohort_start,
    )
    churned_user = User(
        email="metrics-churned@lorevia.app",
        username="metricschurned",
        password_hash="hash",
        created_at=cohort_start + timedelta(days=1),
    )
    reactivated_user = User(
        email="metrics-reactivated@lorevia.app",
        username="metricsreactivated",
        password_hash="hash",
        created_at=cohort_start + timedelta(days=2),
    )
    unresolved_user = User(
        email="metrics-unresolved@lorevia.app",
        username="metricsunresolved",
        password_hash="hash",
        created_at=cohort_start + timedelta(days=3),
    )
    db.add_all([converted_user, churned_user, reactivated_user, unresolved_user])
    await db.flush()

    db.add_all(
        [
            SubscriptionEvent(
                user_id=converted_user.id,
                event_type="subscription_activated",
                source="paddle",
                source_event_id="evt_converted_activate",
                plan="author_monthly",
                status="active",
                occurred_at=cohort_start + timedelta(days=4),
            ),
            SubscriptionEvent(
                user_id=churned_user.id,
                event_type="subscription_canceled",
                source="paddle",
                source_event_id="evt_churned_cancel",
                plan="author_monthly",
                status="canceled",
                occurred_at=cohort_start + timedelta(days=5),
            ),
            SubscriptionEvent(
                user_id=reactivated_user.id,
                event_type="subscription_canceled",
                source="paddle",
                source_event_id="evt_reactivated_cancel",
                plan="author_monthly",
                status="canceled",
                occurred_at=cohort_start + timedelta(days=5),
            ),
            SubscriptionEvent(
                user_id=reactivated_user.id,
                event_type="subscription_activated",
                source="paddle",
                source_event_id="evt_reactivated_activate",
                plan="author_monthly",
                status="active",
                occurred_at=cohort_start + timedelta(days=12),
            ),
            SubscriptionEvent(
                user_id=unresolved_user.id,
                event_type="subscription_canceled",
                source="paddle",
                source_event_id="evt_unresolved_cancel",
                plan="author_monthly",
                status="canceled",
                    occurred_at=now - timedelta(days=5),
                ),
            ]
        )
    await db.commit()

    summary = await build_subscription_metrics_summary(
        db,
        cohort_start=cohort_start.date(),
        cohort_end=now.date(),
        reactivation_window_days=30,
        now=now,
    )

    assert summary.trial_starts == 4
    assert summary.trial_to_paid_conversions == 2
    assert summary.trial_to_paid_rate == 50.0
    assert summary.cancellation_events == 3
    assert summary.resolved_cancellation_events == 2
    assert summary.unresolved_cancellation_events == 1
    assert summary.reactivated_after_cancellation == 1
    assert summary.churned_after_cancellation == 1
    assert summary.post_cancel_churn_rate == 50.0
