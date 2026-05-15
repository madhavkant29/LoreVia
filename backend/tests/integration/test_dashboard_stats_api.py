import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.models.book import Book
from app.models.user import UserWritingActivity


@pytest.mark.asyncio
async def test_books_stats_returns_writing_dashboard_data(client, db, auth_headers, monkeypatch):
    async def _fake_embed_batch(texts: list[str], **_kwargs) -> list[list[float]]:
        return [[0.0] * 1536 for _ in texts]

    monkeypatch.setattr("app.workers.consumers.extraction_consumer.embed_batch", _fake_embed_batch)

    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert me.status_code == 200
    user_id = uuid.UUID(me.json()["id"])

    draft_book = Book(
        user_id=user_id,
        title="Stats Tracker",
        format="manual",
        work_type="novel",
        s3_key="drafts/stats-tracker.txt",
        status="ready",
        mode="author",
    )
    db.add(draft_book)
    await db.commit()
    await db.refresh(draft_book)

    response = await client.post(
        f"/api/v1/books/{draft_book.id}/manuscript/import",
        headers=auth_headers,
        data={
            "text": "One two three four",
            "title": "Chapter 1",
            "chapter_number": "1",
            "replace_existing": "true",
        },
    )
    assert response.status_code == 200

    current = datetime.now(UTC)
    db.add(
        UserWritingActivity(
            user_id=user_id,
            book_id=draft_book.id,
            chapter_number=2,
            entry_title="Chapter 2",
            words_added=600,
            activity_date=(current - timedelta(days=3)).date(),
            created_at=current - timedelta(days=3),
        )
    )
    db.add(
        UserWritingActivity(
            user_id=user_id,
            book_id=draft_book.id,
            chapter_number=3,
            entry_title="Chapter 3",
            words_added=800,
            activity_date=(current - timedelta(days=40)).date(),
            created_at=current - timedelta(days=40),
        )
    )
    await db.commit()

    stats = await client.get("/api/v1/books/stats", headers=auth_headers)
    assert stats.status_code == 200

    payload = stats.json()
    assert payload["writing"]["today"]["words"] == 4
    assert payload["writing"]["last_7_days"]["words"] == 604
    assert payload["writing"]["last_30_days"]["words"] == 604
    assert payload["writing"]["last_year"]["words"] == 1404
    assert payload["private"]["llm_request_count"] == 0
    assert payload["private"]["llm_total_tokens"] == 0
    assert payload["writing"]["entries_today"][0]["title"] == "Chapter 1"
    assert payload["writing"]["entries_today"][0]["words"] == 4
    assert any(day["words"] == 4 for day in payload["writing"]["heatmap"])
