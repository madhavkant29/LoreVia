import uuid

import pytest

from app.models.book import Book, Chapter, Series, SeriesBook
from app.utils.books.manuscript import (
    serialize_manuscript_content,
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
    return {"Cookie": f"lorevia_access_token={token}"}, uuid.UUID(me.json()["id"])


@pytest.mark.asyncio
async def test_world_building_documents_gap_detection_and_notes(client, db, monkeypatch):
    stored: dict[str, bytes] = {}

    def fake_upload_binary(key: str, raw: bytes, content_type: str | None = None) -> str:
        stored[key] = raw
        return key

    def fake_upload_text(key: str, content: str) -> str:
        stored[key] = content.encode("utf-8")
        return key

    def fake_download_book(key: str) -> bytes:
        return stored[key]

    monkeypatch.setattr("app.core.storage.upload_binary", fake_upload_binary)
    monkeypatch.setattr("app.core.storage.upload_text", fake_upload_text)
    monkeypatch.setattr("app.core.storage.download_book", fake_download_book)
    monkeypatch.setattr("app.services.chapter_recovery_service.download_book", fake_download_book)
    monkeypatch.setattr("app.utils.world_building_utils.upload_binary", fake_upload_binary)
    monkeypatch.setattr("app.utils.world_building_utils.download_book", fake_download_book)
    monkeypatch.setattr("app.api.v1.routes.reader.download_book", fake_download_book)
    monkeypatch.setattr("app.api.v1.routes.world_building.download_book", fake_download_book)

    headers, user_id = await _register_user(client, f"world-api-{uuid.uuid4().hex[:8]}@lorevia.app")
    book = Book(
        user_id=user_id,
        title="Worldbook",
        format="pdf",
        s3_key="worldbook.pdf",
        status="ready",
        total_chapters=1,
        mode="author",
    )
    db.add(book)
    await db.flush()

    story_key = f"chapters/{book.id}/1.txt"
    stored[story_key] = serialize_manuscript_content(
        "Northreach is a desert capital where the market roads bake under glass heat.",
        "<p>Northreach is a desert capital where the market roads bake under glass heat.</p>",
    ).encode("utf-8")
    db.add(
        Chapter(
            book_id=book.id,
            number=1,
            title="Salt Market",
            s3_key=story_key,
            word_count=11,
            processed=True,
        )
    )
    await db.commit()

    chapter_before = await client.get(f"/api/v1/reader/{book.id}/chapter/1", headers=headers)
    assert chapter_before.status_code == 200
    assert "desert capital" in (chapter_before.json()["text_content"] or "")

    created_docs = await client.post(
        f"/api/v1/intelligence/{book.id}/world-building/documents",
        headers=headers,
        files={
            "title": (None, "World Bible"),
            "text": (None, "Northreach is a frozen capital ringed by ice gates."),
        },
    )
    assert created_docs.status_code == 200
    first_doc = created_docs.json()[0]
    assert first_doc["title"] == "World Bible"

    second_doc = await client.post(
        f"/api/v1/intelligence/{book.id}/world-building/documents",
        headers=headers,
        data={"title": "Ritual Notes"},
        files={
            "files": (
                "rituals.txt",
                b"The Ember Rite is the kingdom's winter ritual.",
                "text/plain",
            )
        },
    )
    assert second_doc.status_code == 200

    docs_response = await client.get(
        f"/api/v1/intelligence/{book.id}/world-building/documents", headers=headers
    )
    assert docs_response.status_code == 200
    documents = docs_response.json()
    assert len(documents) == 2

    elements_response = await client.get(
        f"/api/v1/intelligence/{book.id}/world-building/elements", headers=headers
    )
    assert elements_response.status_code == 200
    elements = elements_response.json()
    assert any(
        item["name"] == "Northreach" and item["source_scope"] == "worldbuilding"
        for item in elements
    )

    detail_response = await client.get(
        f"/api/v1/intelligence/{book.id}/world-building/documents/{first_doc['id']}",
        headers=headers,
    )
    assert detail_response.status_code == 200
    assert "frozen capital" in detail_response.json()["text"]

    updated_doc = await client.patch(
        f"/api/v1/intelligence/{book.id}/world-building/documents/{first_doc['id']}",
        headers=headers,
        json={
            "title": "World Bible Revised",
            "text": "Northreach is a frozen capital ringed by ice gates.\n\nIts harbor freezes each winter.",
        },
    )
    assert updated_doc.status_code == 200
    assert updated_doc.json()["title"] == "World Bible Revised"

    chapter_after = await client.get(f"/api/v1/reader/{book.id}/chapter/1", headers=headers)
    assert chapter_after.status_code == 200
    assert chapter_after.json()["text_content"] == chapter_before.json()["text_content"]

    gaps = await client.get(f"/api/v1/intelligence/{book.id}/world-building/gaps", headers=headers)
    assert gaps.status_code == 200
    payload = gaps.json()
    assert payload["mode"] == "gap_detection"
    conflict = next(
        (item for item in payload["priority_gaps"] if "Northreach conflicts" in item["title"]), None
    )
    assert conflict is not None
    assert "choose whether" in conflict["suggested_fix"].lower()
    assert "canonical" in conflict["suggested_fix"].lower()
    assert "northreach" in conflict["suggested_fix"].lower()

    created_note = await client.post(
        f"/api/v1/intelligence/{book.id}/world-building/notes",
        headers=headers,
        json={
            "world_document_id": conflict["world_document_id"],
            "note_type": "world_gap",
            "chapter_number": conflict["story_chapter_number"],
            "title": conflict["title"],
            "body": conflict["description"],
            "priority": "critical",
            "status": "open",
            "linked_gap_id": conflict["id"],
            "context_label": conflict["world_document_title"],
            "suggested_fix": conflict["suggested_fix"],
        },
    )
    assert created_note.status_code == 200
    note_id = created_note.json()["id"]

    notes_response = await client.get(
        f"/api/v1/intelligence/{book.id}/world-building/notes", headers=headers
    )
    assert notes_response.status_code == 200
    notes = notes_response.json()
    assert any(note["id"] == note_id for note in notes)

    addressed = await client.patch(
        f"/api/v1/intelligence/{book.id}/world-building/notes/{note_id}/status",
        headers=headers,
        json={"status": "addressed"},
    )
    assert addressed.status_code == 200
    assert addressed.json()["status"] == "addressed"

    reopened = await client.patch(
        f"/api/v1/intelligence/{book.id}/world-building/notes/{note_id}/status",
        headers=headers,
        json={"status": "open"},
    )
    assert reopened.status_code == 200
    assert reopened.json()["status"] == "open"

    override_response = await client.post(
        f"/api/v1/intelligence/{book.id}/world-building/canon-overrides",
        headers=headers,
        json={
            "canonical_name": "Sofya Semyonovna",
            "aliases": ["Sonia", "Sonya"],
            "entity_type": "character",
            "notes": "Merge these names in world gap detection.",
        },
    )
    assert override_response.status_code == 200
    assert override_response.json()["canonical_name"] == "Sofya Semyonovna"

    listed_overrides = await client.get(
        f"/api/v1/intelligence/{book.id}/world-building/canon-overrides",
        headers=headers,
    )
    assert listed_overrides.status_code == 200
    assert any(item["canonical_name"] == "Sofya Semyonovna" for item in listed_overrides.json())


@pytest.mark.asyncio
async def test_series_world_building_analysis_checks_across_member_books(client, db, monkeypatch):
    stored: dict[str, bytes] = {}

    def fake_upload_binary(key: str, raw: bytes, content_type: str | None = None) -> str:
        stored[key] = raw
        return key

    def fake_download_book(key: str) -> bytes:
        return stored[key]

    monkeypatch.setattr("app.core.storage.upload_binary", fake_upload_binary)
    monkeypatch.setattr("app.core.storage.download_book", fake_download_book)
    monkeypatch.setattr("app.services.chapter_recovery_service.download_book", fake_download_book)
    monkeypatch.setattr("app.utils.world_building_utils.upload_binary", fake_upload_binary)
    monkeypatch.setattr("app.utils.world_building_utils.download_book", fake_download_book)
    monkeypatch.setattr("app.api.v1.routes.world_building.download_book", fake_download_book)

    headers, user_id = await _register_user(
        client, f"world-series-api-{uuid.uuid4().hex[:8]}@lorevia.app"
    )
    series = Series(user_id=user_id, name="The Northreach Cycle")
    db.add(series)
    await db.flush()
    first_book = Book(
        user_id=user_id,
        title="Ice Gates",
        format="pdf",
        s3_key="series/ice.pdf",
        status="ready",
        primary_series_id=series.id,
    )
    second_book = Book(
        user_id=user_id,
        title="Glass Market",
        format="pdf",
        s3_key="series/glass.pdf",
        status="ready",
        primary_series_id=series.id,
    )
    db.add_all([first_book, second_book])
    await db.flush()
    db.add_all(
        [
            SeriesBook(series_id=series.id, book_id=first_book.id, position=1),
            SeriesBook(series_id=series.id, book_id=second_book.id, position=2),
        ]
    )
    story_key = f"chapters/{second_book.id}/1.txt"
    stored[story_key] = serialize_manuscript_content(
        "Northreach is a desert capital where the market roads bake under glass heat.",
        "<p>Northreach is a desert capital where the market roads bake under glass heat.</p>",
    ).encode("utf-8")
    db.add(
        Chapter(
            book_id=second_book.id,
            number=1,
            title="Salt Market",
            s3_key=story_key,
            word_count=11,
            processed=True,
        )
    )
    await db.commit()

    created_docs = await client.post(
        f"/api/v1/intelligence/{first_book.id}/world-building/documents",
        headers=headers,
        files={
            "title": (None, "Series Bible"),
            "text": (None, "Northreach is a frozen capital ringed by ice gates."),
        },
    )
    assert created_docs.status_code == 200

    response = await client.get(
        f"/api/v1/intelligence/series/{series.id}/world-building/series-analysis",
        headers=headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["series_id"] == str(series.id)
    assert payload["book_count"] == 2
    assert payload["gap_analysis"]["mode"] == "series_gap_detection"
    assert any(
        item["title"].startswith("Northreach conflicts")
        for item in payload["gap_analysis"]["priority_gaps"]
    )
