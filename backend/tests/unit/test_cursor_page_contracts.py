from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.services import public_catalog_service
from app.utils import reader_utils
from app.utils.books import notes, scene_records, vault_storage


class _Scalars:
    def __init__(self, values):
        self._values = values

    def all(self):
        return list(self._values)


class _Result:
    def __init__(self, *, rows=None, scalars=None):
        self._rows = [] if rows is None else rows
        self._scalars = [] if scalars is None else scalars

    def all(self):
        return list(self._rows)

    def scalars(self):
        return _Scalars(self._scalars)


class _DB:
    def __init__(self, execute_values, *, scalar_values=None):
        self._execute_values = list(execute_values)
        self._scalar_values = list(scalar_values or [])
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        return self._execute_values.pop(0)

    async def scalar(self, statement):
        self.statements.append(statement)
        return self._scalar_values.pop(0)


def _timestamp(offset: int = 0) -> datetime:
    return datetime(2026, 9, 12, 12, 0, tzinfo=UTC) + timedelta(minutes=offset)


def test_cursor_encoders_round_trip_and_reject_malformed_values():
    item_id = uuid.uuid4()
    timestamp = _timestamp()
    timestamp_cursor_pairs = (
        (public_catalog_service.encode_public_book_page_cursor, public_catalog_service.decode_public_book_page_cursor),
        (notes._encode_book_note_page_cursor, notes._decode_book_note_page_cursor),
        (scene_records._encode_novel_scene_page_cursor, scene_records._decode_novel_scene_page_cursor),
        (reader_utils.encode_plot_thread_page_cursor, reader_utils.decode_plot_thread_page_cursor),
    )

    for encoder, decoder in timestamp_cursor_pairs:
        assert decoder(encoder(timestamp, item_id)) == (timestamp, item_id)
        with pytest.raises(HTTPException, match="cursor") as exc_info:
            decoder("not-a-valid-cursor")
        assert exc_info.value.status_code == 400

    vault_cursor = vault_storage._encode_vault_note_page_cursor("Lore/Aria.md", item_id)
    assert vault_storage._decode_vault_note_page_cursor(vault_cursor) == ("Lore/Aria.md", item_id)
    with pytest.raises(HTTPException, match="cursor") as exc_info:
        vault_storage._decode_vault_note_page_cursor("not-a-valid-cursor")
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_note_and_vault_pages_omit_heavy_content_and_emit_next_cursor(monkeypatch):
    book_id = uuid.uuid4()
    user_id = uuid.uuid4()
    book = SimpleNamespace(id=book_id, title="Cursor Story")
    newest_note = SimpleNamespace(
        id=uuid.uuid4(),
        book_id=book_id,
        chapter_number=2,
        title="Newest",
        body="This body must remain detail-only.",
        created_at=_timestamp(2),
        updated_at=_timestamp(2),
    )
    older_note = SimpleNamespace(
        id=uuid.uuid4(),
        book_id=book_id,
        chapter_number=1,
        title="Older",
        body="Older detail.",
        created_at=_timestamp(1),
        updated_at=_timestamp(1),
    )

    async def _note_tags(*_args, **_kwargs):
        return {newest_note.id: ["focus"]}

    monkeypatch.setattr(notes, "list_custom_tags_for_entity_ids", _note_tags)
    notes_db = _DB([_Result(rows=[(newest_note, "Chapter two"), (older_note, "Chapter one")])])
    notes_page = await notes.list_book_notes_page(notes_db, book=book, limit=1)

    assert notes_page["has_more"] is True
    assert notes_page["items"] == [
        {
            "id": str(newest_note.id),
            "book_id": str(book_id),
            "book_title": "Cursor Story",
            "chapter_number": 2,
            "chapter_title": "Chapter two",
            "title": "Newest",
            "body": None,
            "tags": ["focus"],
            "created_at": newest_note.created_at,
            "updated_at": newest_note.updated_at,
        }
    ]
    assert notes._decode_book_note_page_cursor(notes_page["next_cursor"]) == (
        newest_note.updated_at,
        newest_note.id,
    )
    assert "book_notes.body" not in str(notes_db.statements[0])

    newest_vault_note = SimpleNamespace(
        id=uuid.uuid4(),
        book_id=book_id,
        path="Characters/Aria.md",
        source="user_notes",
        content="A long private vault note.",
        created_at=_timestamp(2),
        updated_at=_timestamp(2),
    )
    older_vault_note = SimpleNamespace(
        id=uuid.uuid4(),
        book_id=book_id,
        path="World/Capital.md",
        source="user_notes",
        content="Another long note.",
        created_at=_timestamp(1),
        updated_at=_timestamp(1),
    )
    vault_db = _DB([_Result(scalars=[newest_vault_note, older_vault_note])])
    vault_page = await vault_storage.list_vault_notes_page(
        vault_db,
        book=book,
        user_id=user_id,
        source="user_notes",
        limit=1,
    )

    assert vault_page["has_more"] is True
    assert vault_page["items"][0]["content"] is None
    assert vault_storage._decode_vault_note_page_cursor(vault_page["next_cursor"]) == (
        newest_vault_note.path,
        newest_vault_note.id,
    )
    assert "book_vault_notes.content" not in str(vault_db.statements[0])


@pytest.mark.asyncio
async def test_scene_and_plot_thread_pages_omit_detail_fields_without_lazy_loading(monkeypatch):
    book_id = uuid.uuid4()
    book = SimpleNamespace(id=book_id, title="Cursor Story")
    newest_scene = SimpleNamespace(
        id=uuid.uuid4(),
        book_id=book_id,
        chapter_id=None,
        chapter_number=2,
        title="The gate opens",
        description="A pivotal scene.",
        scene_metadata={"tags": ["draft"]},
        path="scenes/gate.md",
        status="assigned",
        sort_order=1,
        source="manual",
        origin_chapter_number=2,
        created_at=_timestamp(2),
        updated_at=_timestamp(2),
    )
    older_scene = SimpleNamespace(
        id=uuid.uuid4(),
        book_id=book_id,
        chapter_id=None,
        chapter_number=1,
        title="The omen",
        description=None,
        scene_metadata={},
        path="scenes/omen.md",
        status="assigned",
        sort_order=1,
        source="manual",
        origin_chapter_number=1,
        created_at=_timestamp(1),
        updated_at=_timestamp(1),
    )

    async def _scene_tags(*_args, **_kwargs):
        return {newest_scene.id: ["focus"]}

    monkeypatch.setattr(scene_records, "list_custom_tags_for_entity_ids", _scene_tags)
    scenes_db = _DB([_Result(scalars=[newest_scene, older_scene])])
    scenes_page = await scene_records.list_novel_scenes_page(scenes_db, book=book, limit=1)

    assert scenes_page["has_more"] is True
    assert scenes_page["items"][0]["body"] is None
    assert scenes_page["items"][0]["html_body"] is None
    assert scenes_page["items"][0]["tags"] == ["focus"]
    assert "novel_scenes.body" not in str(scenes_db.statements[0])
    assert "novel_scenes.html_body" not in str(scenes_db.statements[0])

    newest_thread = SimpleNamespace(
        id=uuid.uuid4(),
        book_id=book_id,
        title="The hidden gate",
        description="Who can open it?",
        thread_type="mystery",
        status="introduced",
        introduced_at=1,
        last_mentioned_at=2,
        resolved_at=None,
        mention_count=2,
        importance=8,
        created_at=_timestamp(2),
    )
    older_thread = SimpleNamespace(
        id=uuid.uuid4(),
        book_id=book_id,
        title="The lost key",
        description=None,
        thread_type="object",
        status="introduced",
        introduced_at=1,
        last_mentioned_at=1,
        resolved_at=None,
        mention_count=1,
        importance=5,
        created_at=_timestamp(1),
    )

    async def _thread_tags(*_args, **_kwargs):
        return {newest_thread.id: ["main"]}

    monkeypatch.setattr(reader_utils, "list_custom_tags_for_entity_ids", _thread_tags)
    threads_db = _DB(
        [_Result(scalars=[newest_thread, older_thread])], scalar_values=[4]
    )
    threads_page = await reader_utils.list_plot_threads_page(
        threads_db, book_id=book_id, limit=1
    )

    assert threads_page["has_more"] is True
    assert threads_page["items"][0]["title"] == "The hidden gate"
    assert threads_page["items"][0]["tags"] == ["main"]
    assert "note" not in threads_page["items"][0]
    assert "character_ids" not in threads_page["items"][0]
    assert "plot_threads.note" not in str(threads_db.statements[0])
    assert "plot_threads.character_ids" not in str(threads_db.statements[0])


@pytest.mark.asyncio
async def test_public_catalog_page_uses_card_projection_and_caches_first_page(monkeypatch):
    book_id = uuid.uuid4()
    created_at = _timestamp(2)
    book = SimpleNamespace(
        id=book_id,
        user_id=uuid.uuid4(),
        title="Public Cursor Story",
        author="Nora",
        genre="Fantasy",
        format="manual",
        work_type="novel",
        status="ready",
        source_kind="public_demo",
        total_chapters=4,
        is_public=True,
        public_description="A compact public card.",
        public_status="published",
        public_slug="public-cursor-story",
        published_at=created_at,
        public_updated_at=created_at,
        moderation_status="clean",
        content_source_type="user_original",
        source_title=None,
        source_author=None,
        source_public_domain_note=None,
        source_url=None,
        public_share_status="not_requested",
        copyright_warning=False,
        created_at=created_at,
    )
    older_book = SimpleNamespace(**{**book.__dict__, "id": uuid.uuid4(), "created_at": _timestamp(1)})
    cache: dict[str, dict] = {}

    async def _cache_get(key):
        return cache.get(key)

    async def _cache_set(key, payload, ttl):
        assert ttl == 300
        cache[key] = payload

    async def _cache_version():
        return 2

    async def _empty_map(*_args, **_kwargs):
        return {}

    monkeypatch.setattr(public_catalog_service, "cache_get", _cache_get)
    monkeypatch.setattr(public_catalog_service, "cache_set", _cache_set)
    monkeypatch.setattr(public_catalog_service, "get_public_catalog_cache_version", _cache_version)
    monkeypatch.setattr(public_catalog_service, "_active_forum_post_map", _empty_map)
    monkeypatch.setattr(public_catalog_service, "build_public_book_analytics_map", _empty_map)

    db = _DB([_Result(rows=[(book, "nora"), (older_book, "nora")])])
    page = await public_catalog_service.list_public_books_page(db, limit=1)

    assert page.has_more is True
    assert page.items[0].title == "Public Cursor Story"
    assert public_catalog_service.decode_public_book_page_cursor(page.next_cursor) == (
        created_at,
        book_id,
    )
    assert "books.writer_workspace" not in str(db.statements[0])
    assert "books.import_structure" not in str(db.statements[0])

    cached_page = await public_catalog_service.list_public_books_page(_DB([]), limit=1)
    assert cached_page == page
