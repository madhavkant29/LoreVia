import uuid

import pytest

from app.models.book import Book, Chapter
from app.models.character import Character
from app.models.intelligence import ChapterSummary
from app.models.progress import ReadingProgress
from app.services.reader_event_service import sync_reader_events_for_chapter


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
    return {"Cookie": f"lorevia_access_token={token}"}, uuid.UUID(me.json()["id"])


@pytest.mark.asyncio
async def test_book_and_reader_events_endpoints_filter_by_progress(client, db):
    headers, user_id = await _register_user(
        client, f"events-api-{uuid.uuid4().hex[:8]}@lorevia.app"
    )
    book = Book(
        user_id=user_id,
        title="Eventful",
        format="pdf",
        s3_key="eventful.pdf",
        status="ready",
        total_chapters=4,
    )
    db.add(book)
    await db.flush()

    chapter1 = Chapter(book_id=book.id, number=1, title="Arrival", s3_key="chapter-1.txt")
    chapter3 = Chapter(book_id=book.id, number=3, title="Rupture", s3_key="chapter-3.txt")
    hero = Character(
        book_id=book.id,
        name="Mira",
        first_chapter=1,
        growth_events=[
            {
                "chapter_number": 1,
                "event_title": "Takes the oath",
                "description": "Commits to the cause",
                "impact_score": 6,
            },
            {
                "chapter_number": 3,
                "event_title": "Breaks the oath",
                "description": "Turns away",
                "impact_score": 9,
                "is_major": True,
            },
        ],
    )
    db.add_all(
        [
            chapter1,
            chapter3,
            hero,
            ReadingProgress(user_id=user_id, book_id=book.id, current_chapter=1, chapters_read=[1]),
        ]
    )
    await db.flush()
    db.add_all(
        [
            ChapterSummary(
                chapter_id=chapter1.id,
                mode="detailed",
                content="Chapter one summary",
                key_events=[
                    {
                        "event_title": "The oath",
                        "description": "Mira swears service",
                        "importance": 6,
                        "involved_characters": [str(hero.id)],
                    }
                ],
            ),
            ChapterSummary(
                chapter_id=chapter3.id,
                mode="detailed",
                content="Chapter three summary",
                key_events=[
                    {
                        "event_title": "The break",
                        "description": "Mira abandons the order",
                        "importance": 9,
                        "involved_characters": [str(hero.id)],
                    }
                ],
            ),
        ]
    )
    await db.commit()

    all_events = await client.get(f"/api/v1/books/{book.id}/events", headers=headers)
    assert all_events.status_code == 200
    assert len(all_events.json()["major_events"]) == 2

    reader_events = await client.get(f"/api/v1/reader/{book.id}/events", headers=headers)
    assert reader_events.status_code == 200
    items = reader_events.json()["items"]
    assert [item["event_title"] for item in items if item.get("type") == "major"] == ["The oath"]
    assert [item["event_title"] for item in items if item.get("type") == "character"] == [
        "Takes the oath"
    ]


@pytest.mark.asyncio
async def test_reader_events_v2_reads_materialized_rows_with_keyset_pagination(client, db):
    headers, user_id = await _register_user(
        client, f"reader-events-v2-{uuid.uuid4().hex[:8]}@lorevia.app"
    )
    book = Book(
        user_id=user_id,
        title="Materialized events",
        format="pdf",
        s3_key="materialized-events.pdf",
        status="ready",
    )
    db.add(book)
    await db.flush()
    first_chapter = Chapter(
        book_id=book.id,
        number=1,
        title="First",
        s3_key="materialized-events/1.txt",
    )
    second_chapter = Chapter(
        book_id=book.id,
        number=2,
        title="Second",
        s3_key="materialized-events/2.txt",
    )
    progress = ReadingProgress(
        user_id=user_id,
        book_id=book.id,
        current_chapter=2,
        chapters_read=[1, 2],
    )
    db.add_all([first_chapter, second_chapter, progress])
    await db.flush()
    await sync_reader_events_for_chapter(
        db,
        chapter=first_chapter,
        major_events=[
            {"event_title": "Arrival", "description": "The gate opens."},
            {"event_title": "Alliance", "description": "The houses agree."},
        ],
        character_events=[],
    )
    await sync_reader_events_for_chapter(
        db,
        chapter=second_chapter,
        major_events=[{"event_title": "Departure", "description": "The convoy leaves."}],
        character_events=[],
    )
    await db.commit()

    first_response = await client.get(
        f"/api/v1/reader/{book.id}/events/v2?limit=2", headers=headers
    )
    assert first_response.status_code == 200
    first_payload = first_response.json()
    assert first_payload["has_more"] is True
    assert [item["event_title"] for item in first_payload["items"]] == [
        "Alliance",
        "Arrival",
    ]

    second_response = await client.get(
        f"/api/v1/reader/{book.id}/events/v2?limit=2&cursor={first_payload['next_cursor']}",
        headers=headers,
    )
    assert second_response.status_code == 200
    second_payload = second_response.json()
    assert second_payload["has_more"] is False
    assert [item["event_title"] for item in second_payload["items"]] == ["Departure"]
    assert {
        item["id"] for item in first_payload["items"]
    }.isdisjoint({item["id"] for item in second_payload["items"]})

    first_chapter_only = await client.get(
        f"/api/v1/reader/{book.id}/events/v2?chapter=1", headers=headers
    )
    assert first_chapter_only.status_code == 200
    assert [item["chapter_number"] for item in first_chapter_only.json()["items"]] == [1, 1]
