from datetime import UTC, datetime, timedelta
import uuid

import pytest

from app.models.book import Book, Chapter
from app.models.intelligence import ChapterSummary
from app.models.progress import ReadingProgress
from app.models.user import User


async def _register_user(client, email: str) -> tuple[dict[str, str], uuid.UUID]:
    from app.core.security import create_access_token

    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "username": email.split("@")[0][:32],
            "password": "TestPass123!@#",
            "accepted_terms": True,
            "device_id": f"device-{uuid.uuid4().hex}",
        },
    )
    assert response.status_code == 201
    access_token = create_access_token(str(response.json()["id"]))
    return {"Cookie": f"lorevia_access_token={access_token}"}, uuid.UUID(response.json()["id"])


@pytest.mark.asyncio
async def test_free_users_only_get_short_summaries_after_trial(client, db):
    headers, user_id = await _register_user(client, f"pricing-free-{uuid.uuid4().hex[:8]}@lorevia.app")
    user = await db.get(User, user_id)
    assert user is not None
    user.created_at = datetime.now(UTC) - timedelta(days=20)

    book = Book(
        user_id=user_id,
        title="Trial Expired Book",
        format="pdf",
        s3_key="books/trial-expired.pdf",
        status="ready",
        total_chapters=1,
    )
    db.add(book)
    await db.flush()

    chapter = Chapter(
        book_id=book.id,
        number=1,
        title="Chapter 1",
        s3_key="chapters/chapter-1.txt",
        processed=True,
    )
    db.add(chapter)
    await db.flush()
    db.add_all(
        [
            ChapterSummary(chapter_id=chapter.id, mode="short", content="Short summary"),
            ChapterSummary(chapter_id=chapter.id, mode="detailed", content="Detailed summary"),
        ]
    )
    db.add(
        ReadingProgress(
            user_id=user_id,
            book_id=book.id,
            current_chapter=1,
            scroll_pct=1.0,
            chapters_read=[1],
        )
    )
    await db.commit()

    short_response = await client.get(
        f"/api/v1/reader/{book.id}/summary/1",
        headers=headers,
        params={"mode": "short"},
    )
    detailed_response = await client.get(
        f"/api/v1/reader/{book.id}/summary/1",
        headers=headers,
        params={"mode": "detailed"},
    )

    assert short_response.status_code == 200
    assert detailed_response.status_code == 403
    assert detailed_response.json()["detail"] == "Upgrade to Reader to unlock detailed and key-point summaries."


@pytest.mark.asyncio
async def test_reader_users_keep_detailed_summary_access_after_trial_window(client, db):
    headers, user_id = await _register_user(client, f"pricing-reader-{uuid.uuid4().hex[:8]}@lorevia.app")
    user = await db.get(User, user_id)
    assert user is not None
    user.created_at = datetime.now(UTC) - timedelta(days=20)
    user.tier = "reader"

    book = Book(
        user_id=user_id,
        title="Reader Book",
        format="pdf",
        s3_key="books/reader.pdf",
        status="ready",
        total_chapters=1,
    )
    db.add(book)
    await db.flush()

    chapter = Chapter(
        book_id=book.id,
        number=1,
        title="Chapter 1",
        s3_key="chapters/reader-1.txt",
        processed=True,
    )
    db.add(chapter)
    await db.flush()
    db.add(ChapterSummary(chapter_id=chapter.id, mode="detailed", content="Detailed summary"))
    db.add(
        ReadingProgress(
            user_id=user_id,
            book_id=book.id,
            current_chapter=1,
            scroll_pct=1.0,
            chapters_read=[1],
        )
    )
    await db.commit()

    detailed_response = await client.get(
        f"/api/v1/reader/{book.id}/summary/1",
        headers=headers,
        params={"mode": "detailed"},
    )

    assert detailed_response.status_code == 200
