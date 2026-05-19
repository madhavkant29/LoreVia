"""Unit tests for Obsidian vault note persistence helpers."""

import uuid
import zipfile
from io import BytesIO

import pytest
from fastapi import HTTPException

from app.models.book import Book
from app.models.user import User
from app.utils.book_utils import (
    build_obsidian_graph,
    export_obsidian_notes_zip,
    extract_obsidian_wiki_links,
    extract_obsidian_note_references,
    extract_obsidian_tags,
    import_obsidian_notes_zip,
    list_obsidian_notes,
    list_obsidian_note_relations,
    list_obsidian_vault_notes,
    load_obsidian_vault_overrides,
    save_obsidian_vault_note,
)


@pytest.mark.asyncio
async def test_save_list_and_load_obsidian_vault_notes(db):
    user = User(email="vault-notes@lorevia.app", username="vault-notes", password_hash="hash")
    book = Book(
        user=user,
        title="Vault Story",
        format="pdf",
        s3_key="books/vault-story.pdf",
        status="ready",
    )
    db.add_all([user, book])
    await db.commit()

    path = "LoreVia Export - Vault-Story/Characters/Aria.md"
    saved = await save_obsidian_vault_note(
        db,
        book=book,
        user_id=user.id,
        path=path,
        content="# Aria\n\nEdited content",
    )

    assert saved["persisted"] is True
    assert saved["path"] == path
    assert saved["content"] == "# Aria\n\nEdited content"

    notes = await list_obsidian_vault_notes(db, book, user.id)
    assert len(notes) == 1
    assert notes[0]["path"] == path
    assert notes[0]["source"] == "character_bible"
    assert notes[0]["content"] == "# Aria\n\nEdited content"

    overrides = await load_obsidian_vault_overrides(db, book, user.id)
    assert overrides == {path: "# Aria\n\nEdited content"}


@pytest.mark.asyncio
async def test_save_obsidian_vault_note_updates_existing_row(db):
    user = User(email="vault-notes-update@lorevia.app", username="vault-notes-update", password_hash="hash")
    book = Book(
        user=user,
        title="Vault Story",
        format="pdf",
        s3_key="books/vault-story.pdf",
        status="ready",
    )
    db.add_all([user, book])
    await db.commit()

    path = "LoreVia Export - Vault-Story/Characters/Aria.md"
    first = await save_obsidian_vault_note(db, book=book, user_id=user.id, path=path, content="first version")
    second = await save_obsidian_vault_note(db, book=book, user_id=user.id, path=path, content="second version")

    assert first["persisted"] is True
    assert second["persisted"] is True
    assert second["content"] == "second version"

    notes = await list_obsidian_vault_notes(db, book, user.id)
    assert len(notes) == 1
    assert notes[0]["content"] == "second version"


@pytest.mark.asyncio
async def test_user_notes_are_isolated_from_character_bible_notes(db):
    user = User(email="vault-note-sources@lorevia.app", username="vault-note-sources", password_hash="hash")
    book = Book(
        user=user,
        title="Vault Story",
        format="pdf",
        s3_key="books/vault-story.pdf",
        status="ready",
    )
    db.add_all([user, book])
    await db.commit()

    path = "Characters/Aria.md"
    await save_obsidian_vault_note(db, book=book, user_id=user.id, path=path, content="bible", source="character_bible")
    await save_obsidian_vault_note(db, book=book, user_id=user.id, path=path, content="notes", source="user_notes")

    bible_notes = await list_obsidian_vault_notes(db, book, user.id)
    user_notes = await list_obsidian_notes(db, book=book, user_id=user.id, source="user_notes")

    assert len(bible_notes) == 1
    assert len(user_notes) == 1
    assert bible_notes[0]["content"] == "bible"
    assert user_notes[0]["content"] == "notes"


def test_extract_obsidian_wiki_links_and_graph():
    links = extract_obsidian_wiki_links("[[Aria]] meets [[Blaire|B]] and [[World#Lore]].")
    assert links == [
        {"target": "Aria", "alias": "Aria"},
        {"target": "Blaire", "alias": "B"},
        {"target": "World", "alias": "World"},
    ]

    graph = build_obsidian_graph(
        [
            {"path": "Characters/Aria.md", "content": "See [[Blaire]]"},
            {"path": "Characters/Blaire.md", "content": "See [[Aria|Aria Note]]"},
            {"path": "World/Capital.md", "content": "No links"},
        ]
    )
    assert len(graph["nodes"]) == 3
    assert {edge["source"] for edge in graph["edges"]} == {"Characters/Aria.md", "Characters/Blaire.md"}
    assert {edge["target"] for edge in graph["edges"]} == {"Characters/Aria.md", "Characters/Blaire.md"}


def test_extract_obsidian_note_references_and_tags():
    references = extract_obsidian_note_references("![[Aria]] meets [[Blaire|B]] in #World-Building and #plot_notes.")
    assert references == [
        {"target": "Aria", "alias": "Aria", "link_type": "embed"},
        {"target": "Blaire", "alias": "B", "link_type": "reference"},
    ]

    tags = extract_obsidian_tags("#World-Building and #plot_notes with #world-building again")
    assert tags == ["world-building", "plot-notes"]


@pytest.mark.asyncio
async def test_save_obsidian_notes_syncs_links_backlinks_and_tags(db):
    user = User(email="vault-note-relations@lorevia.app", username="vault-note-relations", password_hash="hash")
    book = Book(
        user=user,
        title="Vault Story",
        format="pdf",
        s3_key="books/vault-story.pdf",
        status="ready",
    )
    db.add_all([user, book])
    await db.commit()

    await save_obsidian_vault_note(
        db,
        book=book,
        user_id=user.id,
        path="Characters/Aria.md",
        content="# Aria\n\nSee [[Blaire]] and #world-building.",
        source="user_notes",
    )
    await save_obsidian_vault_note(
        db,
        book=book,
        user_id=user.id,
        path="Characters/Blaire.md",
        content="# Blaire\n\nMentioned by Aria.",
        source="user_notes",
    )

    aria_relations = await list_obsidian_note_relations(db, book=book, user_id=user.id, path="Characters/Aria.md")
    blaire_relations = await list_obsidian_note_relations(db, book=book, user_id=user.id, path="Characters/Blaire.md")

    assert len(aria_relations["links"]) == 1
    assert aria_relations["links"][0]["source_note_path"] == "Characters/Aria.md"
    assert aria_relations["links"][0]["target_note_path"] == "Characters/Blaire.md"
    assert len(aria_relations["tags"]) == 1
    assert aria_relations["tags"][0]["tag_name"] == "world-building"

    assert len(blaire_relations["backlinks"]) == 1
    assert blaire_relations["backlinks"][0]["source_note_path"] == "Characters/Aria.md"
    assert blaire_relations["backlinks"][0]["target_note_path"] == "Characters/Blaire.md"


@pytest.mark.asyncio
async def test_import_and_export_obsidian_user_notes_zip(db):
    user = User(email="vault-note-zip@lorevia.app", username="vault-note-zip", password_hash="hash")
    book = Book(
        user=user,
        title="Vault Story",
        format="pdf",
        s3_key="books/vault-story.pdf",
        status="ready",
    )
    db.add_all([user, book])
    await db.commit()

    archive_buffer = BytesIO()
    with zipfile.ZipFile(archive_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("Characters/Aria.md", "# Aria\n\n[[Blaire]]")
        archive.writestr("World/Capital.md", "# Capital")

    imported = await import_obsidian_notes_zip(
        db,
        book=book,
        user_id=user.id,
        archive_bytes=archive_buffer.getvalue(),
        source="user_notes",
    )
    assert len(imported) == 2

    notes = await list_obsidian_notes(db, book=book, user_id=user.id, source="user_notes")
    exported = export_obsidian_notes_zip(notes=notes)
    with zipfile.ZipFile(BytesIO(exported)) as archive:
        assert sorted(archive.namelist()) == ["Characters/Aria.md", "World/Capital.md"]
        assert archive.read("Characters/Aria.md").decode("utf-8").startswith("# Aria")


@pytest.mark.asyncio
async def test_import_obsidian_notes_zip_rejects_suspicious_compression(db, monkeypatch):
    user = User(email="vault-note-zip-guard@lorevia.app", username="vault-note-zip-guard", password_hash="hash")
    book = Book(
        user=user,
        title="Vault Story",
        format="pdf",
        s3_key="books/vault-story.pdf",
        status="ready",
    )
    db.add_all([user, book])
    await db.commit()

    monkeypatch.setattr("app.core.config.settings.UPLOAD_ARCHIVE_MAX_COMPRESSION_RATIO", 2, raising=False)

    archive_buffer = BytesIO()
    with zipfile.ZipFile(archive_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("Characters/Aria.md", b"A" * 5000)

    with pytest.raises(HTTPException) as exc_info:
        await import_obsidian_notes_zip(
            db,
            book=book,
            user_id=user.id,
            archive_bytes=archive_buffer.getvalue(),
            source="user_notes",
        )

    assert "unsafe compressed file" in str(exc_info.value.detail)
