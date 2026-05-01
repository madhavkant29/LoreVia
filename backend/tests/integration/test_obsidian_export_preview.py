"""Integration tests for the Obsidian export preview endpoint."""

import io
import uuid
import zipfile

import pytest

from app.api.deps.auth import get_current_user
from app.main import app
from app.models.book import Book, Chapter, NoteSeriesLink, ObsidianVaultNote, Series
from app.models.character import Character
from app.models.intelligence import ChapterSummary, PlotThread, WikiEntry
from app.models.user import User


async def _build_obsidian_preview_book(db):
    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"obsidian-preview-{suffix}@lorevia.app",
        username=f"obsidian-preview-{suffix}",
        password_hash="hash",
    )
    db.add(user)
    await db.flush()

    book = Book(
        user_id=user.id,
        title="Preview Story",
        format="pdf",
        s3_key="books/preview-story.pdf",
        status="ready",
    )
    db.add(book)
    await db.flush()

    aria = Character(
        book_id=book.id,
        name="Aria",
        role="mc",
        first_chapter=1,
        mention_count=5,
        trait_state={},
        personality_tags=["curious"],
        motivations=["find the truth"],
        fears=["losing Blaire"],
        arc_summary="Aria pushes toward the truth.",
    )
    blaire = Character(
        book_id=book.id,
        name="Blaire",
        role="sc",
        first_chapter=2,
        mention_count=3,
        trait_state={},
        personality_tags=["calm"],
        arc_summary="Blaire steadies the search.",
    )
    db.add_all([aria, blaire])
    await db.flush()

    chapter_one = Chapter(
        book_id=book.id,
        number=1,
        title="Arrival",
        s3_key="chapters/1.txt",
    )
    db.add(chapter_one)
    await db.flush()
    db.add(
        ChapterSummary(
            chapter_id=chapter_one.id,
            mode="short",
            content="Aria reaches the capital.",
            key_events=[
                {
                    "event": "Aria arrives",
                    "description": "Aria arrives in the capital with Blaire.",
                    "importance": 9,
                    "involved_characters": ["Aria", "Blaire"],
                }
            ],
        )
    )
    db.add(
        PlotThread(
            book_id=book.id,
            title="The Hidden Map",
            status="ongoing",
            importance=8,
            introduced_at=1,
            note="Aria and Blaire pursue the map.",
            character_ids=["Aria", "Blaire"],
        )
    )
    db.add(
        WikiEntry(
            book_id=book.id,
            entry_type="location",
            name="The Capital",
            description="Aria and Blaire meet in the capital.",
            first_mention=1,
            related_char_ids=[str(aria.id), str(blaire.id)],
        )
    )
    await db.commit()
    return user, book


async def _build_obsidian_series_link(db):
    user = User(
        email="obsidian-series@lorevia.app",
        username="obsidian-series",
        password_hash="hash",
    )
    db.add(user)
    await db.flush()

    source_book = Book(
        user_id=user.id,
        title="Source Book",
        format="pdf",
        s3_key="books/source.pdf",
        status="ready",
    )
    target_book = Book(
        user_id=user.id,
        title="Target Book",
        format="pdf",
        s3_key="books/target.pdf",
        status="ready",
    )
    series = Series(
        user_id=user.id,
        name="Series One",
    )
    db.add_all([source_book, target_book, series])
    await db.flush()

    source_note = ObsidianVaultNote(
        user_id=user.id,
        book_id=source_book.id,
        path="Characters/Aria.md",
        source="user_notes",
        content="# Aria",
    )
    target_note = ObsidianVaultNote(
        user_id=user.id,
        book_id=target_book.id,
        path="Characters/Blaire.md",
        source="user_notes",
        content="# Blaire",
    )
    db.add_all([source_note, target_note])
    await db.flush()

    link = NoteSeriesLink(
        user_id=user.id,
        series_id=series.id,
        source_book_id=source_book.id,
        target_book_id=target_book.id,
        source_note_id=source_note.id,
        target_note_id=target_note.id,
        link_type="reference",
    )
    db.add(link)
    await db.commit()
    await db.refresh(source_book)
    await db.refresh(target_book)
    return source_book, target_book, link


@pytest.mark.asyncio
async def test_obsidian_bible_preview_returns_folder_manifest(client, db):
    user, book = await _build_obsidian_preview_book(db)

    async def override_current_user():
        return user

    app.dependency_overrides[get_current_user] = override_current_user
    try:
        response = await client.get(f"/api/v1/books/{book.id}/export/character-bible/preview")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["root_folder"] == "LoreVia Export - Preview-Story"
    assert payload["files"][0]["path"].endswith("000 - Index.md")
    assert any(file["path"].endswith("Characters/Aria.md") for file in payload["files"])
    assert any(file["path"].endswith("Major Events/Aria-arrives.md") for file in payload["files"])
    assert any("[[Blaire]]" in file["content"] for file in payload["files"] if file["path"].endswith("Characters/Aria.md"))


@pytest.mark.asyncio
async def test_obsidian_note_series_links_are_bound_to_source_book(db):
    source_book, target_book, link = await _build_obsidian_series_link(db)

    assert len(source_book.obsidian_note_series_links) == 1
    assert source_book.obsidian_note_series_links[0].id == link.id
    assert source_book.obsidian_note_series_links[0].source_book_id == source_book.id
    assert target_book.obsidian_note_series_links == []


@pytest.mark.asyncio
async def test_obsidian_bible_notes_save_is_visible_in_preview_and_notes_list(client, db):
    user, book = await _build_obsidian_preview_book(db)

    async def override_current_user():
        return user

    app.dependency_overrides[get_current_user] = override_current_user
    try:
        preview_before = await client.get(f"/api/v1/books/{book.id}/export/character-bible/preview")
        assert preview_before.status_code == 200
        baseline = preview_before.json()
        target_path = next(file["path"] for file in baseline["files"] if file["path"].endswith("Characters/Aria.md"))

        save_response = await client.put(
            f"/api/v1/books/{book.id}/export/character-bible/notes",
            json={"path": target_path, "content": "# Aria\n\nEdited in app"},
        )
        assert save_response.status_code == 200
        assert save_response.json()["persisted"] is True

        preview_after = await client.get(f"/api/v1/books/{book.id}/export/character-bible/preview")
        assert preview_after.status_code == 200
        updated = preview_after.json()
        updated_aria = next(file for file in updated["files"] if file["path"] == target_path)
        assert "Edited in app" in updated_aria["content"]

        notes_response = await client.get(f"/api/v1/books/{book.id}/export/character-bible/notes")
        assert notes_response.status_code == 200
        notes = notes_response.json()
        assert len(notes) == 1
        assert notes[0]["path"] == target_path
        assert "Edited in app" in notes[0]["content"]
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_user_obsidian_notes_crud_graph_and_export(client, db):
    user, book = await _build_obsidian_preview_book(db)

    async def override_current_user():
        return user

    app.dependency_overrides[get_current_user] = override_current_user
    try:
        save_one = await client.put(
            f"/api/v1/books/{book.id}/notes/obsidian",
            json={"path": "Characters/Aria.md", "content": "# Aria\n\nLinks to [[Blaire]]."},
        )
        assert save_one.status_code == 200
        assert save_one.json()["source"] == "user_notes"

        save_two = await client.put(
            f"/api/v1/books/{book.id}/notes/obsidian",
            json={"path": "Characters/Blaire.md", "content": "# Blaire"},
        )
        assert save_two.status_code == 200

        list_response = await client.get(f"/api/v1/books/{book.id}/notes/obsidian")
        assert list_response.status_code == 200
        notes = list_response.json()
        assert len(notes) == 2

        graph_response = await client.get(f"/api/v1/books/{book.id}/notes/obsidian/graph")
        assert graph_response.status_code == 200
        graph = graph_response.json()
        assert len(graph["nodes"]) == 2
        assert graph["edges"][0]["source"] == "Characters/Aria.md"
        assert graph["edges"][0]["target"] == "Characters/Blaire.md"

        relations_response = await client.get(
            f"/api/v1/books/{book.id}/notes/obsidian/relations",
            params={"path": "Characters/Aria.md"},
        )
        assert relations_response.status_code == 200
        relations = relations_response.json()
        assert len(relations["links"]) == 1
        assert relations["links"][0]["target_note_path"] == "Characters/Blaire.md"
        assert relations["tags"] == []

        export_response = await client.get(f"/api/v1/books/{book.id}/notes/obsidian/export")
        assert export_response.status_code == 200
        with zipfile.ZipFile(io.BytesIO(export_response.content)) as archive:
            assert sorted(archive.namelist()) == ["Characters/Aria.md", "Characters/Blaire.md"]

        delete_response = await client.delete(f"/api/v1/books/{book.id}/notes/obsidian/Characters/Blaire.md")
        assert delete_response.status_code == 204
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_user_obsidian_notes_import_zip(client, db):
    user, book = await _build_obsidian_preview_book(db)

    async def override_current_user():
        return user

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("Plot/Thread.md", "# Thread\n\n[[Characters]]")
        archive.writestr("Characters.md", "# Characters")

    app.dependency_overrides[get_current_user] = override_current_user
    try:
        response = await client.post(
            f"/api/v1/books/{book.id}/notes/obsidian/import",
            files={"file": ("vault.zip", buffer.getvalue(), "application/zip")},
        )
        assert response.status_code == 200
        payload = response.json()
        assert len(payload) == 2
        assert {item["path"] for item in payload} == {"Plot/Thread.md", "Characters.md"}
        assert all(item["source"] == "user_notes" for item in payload)
    finally:
        app.dependency_overrides.pop(get_current_user, None)
