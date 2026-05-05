import uuid

import pytest

from app.models.book import Book, Chapter
from app.models.intelligence import PlotThread
from app.models.progress import ReadingProgress


async def _register_user(client, email: str) -> tuple[dict[str, str], uuid.UUID]:
    from app.core.security import create_access_token

    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "username": email.split("@")[0][:24],
            "password": "StrongPass123!@#",
            "accepted_terms": True,
        },
    )
    assert response.status_code == 201
    token = create_access_token(str(response.json()["id"]))
    assert token
    me = await client.get("/api/v1/auth/me", headers={"Cookie": f"lorevia_access_token={token}"})
    assert me.status_code == 200
    return {"Cookie": f"lorevia_access_token={token}"}, uuid.UUID(me.json()["id"])


@pytest.mark.asyncio
async def test_reader_timeline_keeps_plot_threads_visible_when_progress_is_sparse(client, db):
    headers, user_id = await _register_user(client, f"timeline-api-{uuid.uuid4().hex[:8]}@lorevia.app")

    book = Book(
        user_id=user_id,
        title="Threaded",
        format="pdf",
        s3_key="threaded.pdf",
        status="ready",
        total_chapters=3,
        mode="reader",
    )
    db.add(book)
    await db.flush()

    db.add_all(
        [
            Chapter(book_id=book.id, number=1, title="Spark", s3_key="chapter-1.txt"),
            Chapter(book_id=book.id, number=2, title="Pressure", s3_key="chapter-2.txt"),
            Chapter(book_id=book.id, number=3, title="Crossroads", s3_key="chapter-3.txt"),
            PlotThread(
                book_id=book.id,
                title="The buried ledger",
                status="ongoing",
                introduced_at=1,
                importance=8,
                description="A hidden ledger keeps reshaping the investigation.",
            ),
            ReadingProgress(
                user_id=user_id,
                book_id=book.id,
                current_chapter=3,
                chapters_read=[3],
            ),
        ]
    )
    await db.commit()

    response = await client.get(f"/api/v1/reader/{book.id}/timeline", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert [chapter["number"] for chapter in payload["chapters"]] == [1, 2, 3]
    assert [track["title"] for track in payload["thread_tracks"]] == ["The buried ledger"]
    assert payload["thread_tracks"][0]["start_chapter"] == 1
    assert payload["thread_tracks"][0]["end_chapter"] == 3
