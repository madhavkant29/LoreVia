import uuid

import pytest

from app.models.book import Book, Chapter, Series
from app.models.character import Character


async def _register_user(client, email: str) -> tuple[dict[str, str], uuid.UUID]:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "testpass123"},
    )
    assert response.status_code == 201
    payload = response.json()
    me_response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {payload['access_token']}"},
    )
    assert me_response.status_code == 200
    return {"Authorization": f"Bearer {payload['access_token']}"}, uuid.UUID(me_response.json()["id"])


@pytest.mark.asyncio
async def test_character_routes_do_not_leak_across_users(client, db):
    owner_headers, owner_id = await _register_user(client, "owner-access@lorevia.app")
    intruder_headers, _ = await _register_user(client, "intruder-access@lorevia.app")

    owner_book = Book(
        user_id=owner_id,
        title="Private Book",
        format="pdf",
        s3_key="private/book.pdf",
        status="ready",
    )
    db.add(owner_book)
    await db.flush()

    character = Character(
        book_id=owner_book.id,
        name="Hidden Character",
        first_chapter=1,
        trait_state={"mood": "guarded"},
    )
    db.add(character)
    await db.commit()

    direct = await client.get(f"/api/v1/characters/{character.id}", headers=intruder_headers)
    state = await client.get(
        f"/api/v1/characters/{character.id}/state",
        headers=intruder_headers,
        params={"chapter": 1},
    )

    assert direct.status_code == 404
    assert state.status_code == 404

    owner_visible = await client.get(f"/api/v1/characters/{character.id}", headers=owner_headers)
    assert owner_visible.status_code == 200


@pytest.mark.asyncio
async def test_series_routes_require_book_ownership(client, db):
    owner_headers, owner_id = await _register_user(client, "owner-series@lorevia.app")
    intruder_headers, intruder_id = await _register_user(client, "intruder-series@lorevia.app")

    owner_book = Book(
        user_id=owner_id,
        title="Owner Book",
        format="pdf",
        s3_key="owner/book.pdf",
        status="ready",
        total_chapters=3,
    )
    owner_series = Series(user_id=owner_id, name="Owner Saga")
    intruder_series = Series(user_id=intruder_id, name="Intruder Saga")
    db.add_all([owner_book, owner_series, intruder_series])
    await db.commit()

    add_to_foreign_series = await client.post(
        f"/api/v1/books/series/{owner_series.id}/books/{owner_book.id}",
        headers=intruder_headers,
        json={"position": 1},
    )
    add_foreign_book = await client.post(
        f"/api/v1/books/series/{intruder_series.id}/books/{owner_book.id}",
        headers=intruder_headers,
        json={"position": 1},
    )

    assert add_to_foreign_series.status_code == 404
    assert add_foreign_book.status_code == 404


@pytest.mark.asyncio
async def test_mark_book_read_updates_only_current_user_progress(client, db):
    owner_headers, owner_id = await _register_user(client, "owner-progress@lorevia.app")
    intruder_headers, _ = await _register_user(client, "intruder-progress@lorevia.app")

    book = Book(
        user_id=owner_id,
        title="Series Volume",
        format="pdf",
        s3_key="series/volume.pdf",
        status="ready",
        total_chapters=4,
    )
    series = Series(user_id=owner_id, name="Long Saga")
    db.add_all([book, series])
    await db.flush()

    for number in range(1, 5):
        db.add(Chapter(book_id=book.id, number=number, title=f"Chapter {number}", s3_key=f"chapter-{number}.txt"))
    await db.commit()

    response = await client.post(
        f"/api/v1/books/series/{series.id}/books/{book.id}",
        headers=owner_headers,
        json={"position": 1},
    )
    assert response.status_code == 200

    marked = await client.put(
        f"/api/v1/books/series/{series.id}/books/{book.id}/status",
        headers=owner_headers,
        json={"marked_complete": True},
    )
    assert marked.status_code == 200
    assert marked.json()["progress_pct"] == 100.0

    owner_progress = await client.get(f"/api/v1/reader/{book.id}/progress", headers=owner_headers)
    intruder_progress = await client.get(f"/api/v1/reader/{book.id}/progress", headers=intruder_headers)

    assert owner_progress.status_code == 200
    assert owner_progress.json()["percent_complete"] == 100.0
    assert intruder_progress.status_code == 404


@pytest.mark.asyncio
async def test_progress_write_routes_require_book_ownership(client, db):
    owner_headers, owner_id = await _register_user(client, "owner-write-progress@lorevia.app")
    intruder_headers, _ = await _register_user(client, "intruder-write-progress@lorevia.app")

    book = Book(
        user_id=owner_id,
        title="Locked Progress Book",
        format="pdf",
        s3_key="locked/progress.pdf",
        status="ready",
        total_chapters=2,
    )
    db.add(book)
    await db.flush()
    db.add(Chapter(book_id=book.id, number=1, title="Chapter 1", s3_key="chapter-1.txt"))
    db.add(Chapter(book_id=book.id, number=2, title="Chapter 2", s3_key="chapter-2.txt"))
    await db.commit()

    update_progress = await client.put(
        f"/api/v1/reader/{book.id}/progress",
        headers=intruder_headers,
        params={"current_chapter": 1, "scroll_pct": 0.5},
    )
    update_chapter = await client.put(
        f"/api/v1/reader/{book.id}/progress/chapter-status",
        headers=intruder_headers,
        params={"chapter": 1, "read": True},
    )

    assert update_progress.status_code == 404
    assert update_chapter.status_code == 404
