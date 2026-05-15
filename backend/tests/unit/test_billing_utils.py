import pytest
from fastapi import HTTPException

from app.models.book import Book, Series, SeriesBook
from app.models.intelligence import WorldBuildingDocument
from app.models.user import User
from app.utils.billing_utils import (
    calculate_upload_usage_summary,
    ensure_upload_capacity,
    paddle_plan_from_event_data,
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


def test_paddle_plan_from_event_data_does_not_default_unknown_events_to_reader():
    assert paddle_plan_from_event_data({"items": []}) == ""
