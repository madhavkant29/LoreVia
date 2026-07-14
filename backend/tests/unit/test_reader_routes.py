from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from tests.unit.route_patch_helpers import patch_route_dependency
from tests.unit.route_facades import reader
from app.schemas.reader import SaveQuoteBody, UpdatePlotThreadBody


class _ScalarList:
    def __init__(self, items):
        self._items = items

    def all(self):
        return list(self._items)

    def first(self):
        return self._items[0] if self._items else None


class _Result:
    def __init__(self, *, scalar=None, all_rows=None, scalars=None):
        self._scalar = scalar
        self._all_rows = [] if all_rows is None else all_rows
        self._scalars = [] if scalars is None else scalars

    def scalar(self):
        return self._scalar

    def all(self):
        return list(self._all_rows)

    def scalars(self):
        return _ScalarList(self._scalars)


class _FakeDB:
    def __init__(self, *, get_values=None, execute_values=None, scalar_values=None):
        self._get_values = list(get_values or [])
        self._execute_values = list(execute_values or [])
        self._scalar_values = list(scalar_values or [])
        self.added = []
        self.commits = 0
        self.rollbacks = 0
        self.refreshed = []

    async def get(self, *_args, **_kwargs):
        return self._get_values.pop(0)

    async def execute(self, *_args, **_kwargs):
        return self._execute_values.pop(0)

    async def scalar(self, *_args, **_kwargs):
        return self._scalar_values.pop(0)

    def add(self, item):
        self.added.append(item)
        if getattr(item, "id", None) is None:
            item.id = uuid.uuid4()

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1

    async def refresh(self, item):
        self.refreshed.append(item)


def _user(user_id: uuid.UUID):
    return SimpleNamespace(id=user_id, tier="reader", email="reader@example.com")


def _book(*, user_id: uuid.UUID, total_chapters: int = 6, mode: str = "reader", fmt: str = "epub"):
    return SimpleNamespace(
        id=uuid.uuid4(),
        user_id=user_id,
        title="Atlas",
        total_chapters=total_chapters,
        mode=mode,
        format=fmt,
        is_public=False,
        is_truncated=False,
        total_tokens=0,
    )


class _RollbackSensitiveBook:
    def __init__(
        self, *, book_id: uuid.UUID, user_id: uuid.UUID, db: _FakeDB, title: str = "Atlas"
    ):
        self.id = book_id
        self.user_id = user_id
        self._db = db
        self._title = title

    @property
    def title(self):
        if self._db.rollbacks > 0:
            raise AssertionError("title was accessed after rollback")
        return self._title


def _async_value(value):
    async def _inner(*_args, **_kwargs):
        return value

    return _inner


@pytest.mark.asyncio
async def test_search_uses_reader_specific_retrieval_settings(monkeypatch):
    user_id = uuid.uuid4()
    book = _book(user_id=user_id, total_chapters=8)
    captured: dict[str, object] = {}

    async def _fake_access(*_args, **_kwargs):
        return book, None

    async def _fake_cache_get(_key):
        return None

    async def _fake_cache_set(*_args, **_kwargs):
        return None

    async def _fake_semantic_search(*_args, **kwargs):
        captured.update(kwargs)
        return [{"chapter_num": 3, "chapter_title": "Storm", "text": "Result", "relevance": 0.9}]

    patch_route_dependency(monkeypatch, reader, "get_book_with_collaboration_access", _fake_access)
    patch_route_dependency(monkeypatch, reader, "collaboration_allows_chapter", lambda *_args, **_kwargs: True)
    patch_route_dependency(monkeypatch, reader, "cache_get", _fake_cache_get)
    patch_route_dependency(monkeypatch, reader, "cache_set", _fake_cache_set)
    patch_route_dependency(monkeypatch, reader, "semantic_search", _fake_semantic_search)

    payload = await reader.search(
        book.id, q="storm clue", chapter=3, db=_FakeDB(), current_user=_user(user_id), _=None
    )

    assert payload[0]["chapter_num"] == 3
    assert captured["limit"] == 4
    assert captured["candidate_limit"] == 10
    assert captured["similarity_threshold"] == 0.55


def test_reader_route_helpers_normalize_payloads():
    assert reader._clean_text(" <b>Hello</b> ") == "Hello"
    major = reader._normalize_reader_major_event(
        3,
        "Storm",
        {
            "event_title": "Key Falls",
            "description": "The silver key drops.",
            "importance": 8,
            "involved_characters": ["a"],
            "event_type": "plot",
        },
        {"a": "Iris"},
    )
    assert major["involved_character_names"] == ["Iris"]

    character = SimpleNamespace(id=uuid.uuid4(), name="Iris", first_chapter=1, role="mc")
    event = reader._normalize_reader_character_event(
        character,
        {"event": "Learns truth", "impact": "Shift", "importance": 7, "growth_direction": "up"},
    )
    assert event["character_name"] == "Iris"
    assert event["growth_direction"] == "up"


@pytest.mark.asyncio
async def test_get_chapter_media_public_validates_token_and_download(monkeypatch):
    media_id = uuid.uuid4()
    user_id = uuid.uuid4()
    media = SimpleNamespace(
        id=media_id, book_id=uuid.uuid4(), storage_key="media.bin", content_type="image/png"
    )
    book = SimpleNamespace(id=media.book_id, user_id=user_id)

    monkeypatch.setattr("app.core.config.settings.PUBLIC_MODE_ENABLED", False, raising=False)
    with pytest.raises(HTTPException) as exc:
        await reader.get_chapter_media_public(media_id, token="bad", db=_FakeDB())
    assert exc.value.status_code == 503
    monkeypatch.setattr("app.core.config.settings.PUBLIC_MODE_ENABLED", True, raising=False)

    db = _FakeDB(get_values=[media, book])
    patch_route_dependency(monkeypatch, reader, "decode_token", lambda _token: None)
    with pytest.raises(HTTPException) as exc:
        await reader.get_chapter_media_public(media_id, token="bad", db=db)
    assert exc.value.status_code == 401

    db = _FakeDB(get_values=[media, book])
    monkeypatch.setattr(
        reader,
        "decode_token",
        lambda _token: {"type": "asset", "sub": str(user_id), "res": f"chapter-media:{media_id}"},
    )
    patch_route_dependency(monkeypatch, reader, "download_book", lambda _key: b"png")
    response = await reader.get_chapter_media_public(media_id, token="ok", db=db)
    assert response.media_type == "image/png"


@pytest.mark.asyncio
async def test_get_chapter_supports_fallback_and_stored_content(monkeypatch):
    user_id = uuid.uuid4()
    book = _book(user_id=user_id, total_chapters=8, fmt="pdf")
    db = _FakeDB(
        get_values=[book],
        execute_values=[_Result(scalar=None), _Result(scalars=[]), _Result(scalars=[])],
    )
    patch_route_dependency(monkeypatch, reader, "consolidate_characters", lambda *_args, **_kwargs: None)

    async def _fake_consolidate(*_args, **_kwargs):
        return None

    patch_route_dependency(monkeypatch, reader, "consolidate_characters", _fake_consolidate)

    async def _fake_resolve_missing(*_args, **_kwargs):
        return {
            "chapter_title": "Fallback",
            "content_version": None,
            "text_url": None,
            "text_content": "Fallback text",
            "html_content": None,
            "media": [{"count": 1}],
            "analysis_status": None,
            "source_integrity": None,
        }

    patch_route_dependency(monkeypatch, reader, "resolve_reader_chapter_payload", _fake_resolve_missing)

    async def _fake_available(*_args, **_kwargs):
        return True

    patch_route_dependency(monkeypatch, reader, "chapter_intelligence_available", _fake_available)
    monkeypatch.setattr(
        reader, "backfill_character_first_chapters_for_chapter_text", _async_value(False)
    )
    patch_route_dependency(monkeypatch, reader, "get_custom_tags_for_entity", _async_value([]))

    payload = await reader.get_chapter(book.id, 2, db=db, current_user=_user(user_id))
    assert payload["chapter_title"] == "Fallback"
    assert payload["text_content"] == "Fallback text"
    assert payload["can_copy_manuscript"] is True
    assert payload["analysis_status"] is None

    chapter_id = uuid.uuid4()
    chapter = SimpleNamespace(
        id=chapter_id,
        book_id=book.id,
        number=2,
        title="Stored",
        s3_key="stored.json",
        content_version=3,
        analysis_state={
            "status": "queued",
            "generated_modes": [],
            "attempt_count": 1,
            "source_integrity": {
                "text_present": True,
                "media_marker_count": 1,
                "stored_media_count": 0,
                "recovery_status": "ok",
            },
        },
    )
    character = SimpleNamespace(
        id=uuid.uuid4(),
        name="Iris",
        aliases=[],
        role="mc",
        first_chapter=1,
        archetype="hero",
        personality_tags=["brave"],
        trait_state={"eyes": "blue"},
        arc_summary="steady",
        motivations=[],
    )
    state = SimpleNamespace(character_id=character.id, trait_snapshot={"eyes": "green"})
    db = _FakeDB(
        get_values=[book],
        execute_values=[
            _Result(scalar=chapter),
            _Result(scalars=[character]),
            _Result(scalars=[state]),
            _Result(all_rows=[]),
        ],
    )

    async def _fake_resolve_stored(*_args, **_kwargs):
        return {
            "chapter_title": "Stored",
            "content_version": 3,
            "text_url": "url:stored.json",
            "text_content": "[[IMAGE:1]] recovered",
            "html_content": "<p>body</p>",
            "media": [{"count": 1}],
            "analysis_status": {
                "status": "queued",
                "generated_modes": [],
                "attempt_count": 1,
                "last_error": None,
                "updated_at": None,
            },
            "source_integrity": {
                "text_present": True,
                "media_marker_count": 1,
                "stored_media_count": 0,
                "recovery_status": "ok",
                "last_recovery_error": None,
                "updated_at": None,
            },
        }

    patch_route_dependency(monkeypatch, reader, "resolve_reader_chapter_payload", _fake_resolve_stored)
    monkeypatch.setattr(
        reader,
        "serialize_reader_character",
        lambda char, trait_snapshot=None, **_kwargs: {
            "id": str(char.id),
            "name": char.name,
            "aliases": [],
            "role": char.role,
            "first_chapter": char.first_chapter,
            "description": f"{char.archetype}:{trait_snapshot['eyes']}",
            "trait_state": trait_snapshot or {},
            "personality_tags": char.personality_tags or [],
            "motivations": char.motivations or [],
            "fears": [],
            "archetype": char.archetype,
            "arc_summary": char.arc_summary,
            "mention_count": 0,
            "is_manual": False,
            "analysis_metadata": {"confidence_band": "medium"},
        },
    )
    patch_route_dependency(monkeypatch, reader, "get_custom_tags_for_entity", _async_value([]))

    payload = await reader.get_chapter(book.id, 2, db=db, current_user=_user(user_id))
    assert payload["text_url"] == "url:stored.json"
    assert payload["chapter_title"] == "Stored"
    assert payload["characters"][0]["description"] == "hero:green"
    assert payload["characters"][0]["analysis_metadata"]["confidence_band"] == "medium"
    assert payload["can_copy_manuscript"] is True
    assert payload["analysis_status"]["status"] == "queued"
    assert payload["source_integrity"]["recovery_status"] == "ok"


@pytest.mark.asyncio
async def test_get_chapter_uses_manual_scene_workspace_when_body_is_placeholder(monkeypatch):
    user_id = uuid.uuid4()
    book = _book(user_id=user_id, total_chapters=4, fmt="pdf")
    chapter = SimpleNamespace(
        id=uuid.uuid4(),
        book_id=book.id,
        number=2,
        title="Chapter 2",
        s3_key="stored.json",
        content_version=1,
    )
    db = _FakeDB(
        get_values=[book],
        execute_values=[
            _Result(scalar=chapter),
            _Result(scalars=[]),
            _Result(scalars=[]),
        ],
    )

    async def _fake_consolidate(*_args, **_kwargs):
        return None

    async def _fake_available(*_args, **_kwargs):
        return True

    patch_route_dependency(monkeypatch, reader, "consolidate_characters", _fake_consolidate)
    monkeypatch.setattr(
        reader, "backfill_character_first_chapters_for_chapter_text", _async_value(False)
    )
    patch_route_dependency(monkeypatch, reader, "chapter_intelligence_available", _fake_available)
    patch_route_dependency(monkeypatch, reader, "get_custom_tags_for_entity", _async_value([]))

    async def _fake_resolve_placeholder(*_args, **_kwargs):
        return {
            "chapter_title": "Chapter 2",
            "content_version": 1,
            "text_url": "url:stored.json",
            "text_content": "## Scene 1 - Arrival\n\nPOV: Mira\n\nThe boat scraped against the pier.",
            "html_content": "<p>The boat scraped against the pier.</p>",
            "media": [],
            "analysis_status": None,
            "source_integrity": None,
        }

    patch_route_dependency(monkeypatch, reader, "resolve_reader_chapter_payload", _fake_resolve_placeholder)

    payload = await reader.get_chapter(book.id, 2, db=db, current_user=_user(user_id))

    assert payload["text_content"].startswith("## Scene 1 - Arrival")
    assert "POV: Mira" in payload["text_content"]
    assert "The boat scraped against the pier." in payload["text_content"]
    assert "boat scraped" in (payload["html_content"] or "")


@pytest.mark.asyncio
async def test_get_chapter_blocks_copy_for_private_read_only_shares(monkeypatch):
    user_id = uuid.uuid4()
    collaborator = SimpleNamespace(
        role="beta_reader",
        scope={"chapter_start": 1, "chapter_end": 3},
        permissions={"can_edit_manuscript": False, "can_view_selected_chapters_only": True},
    )
    book = _book(user_id=uuid.uuid4(), total_chapters=3, fmt="epub")
    chapter = SimpleNamespace(
        id=uuid.uuid4(),
        book_id=book.id,
        number=2,
        title="Chapter 2",
        s3_key="stored.json",
        content_version=1,
    )
    db = _FakeDB(
        execute_values=[
            _Result(scalar=chapter),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
        ],
    )

    async def _fake_consolidate(*_args, **_kwargs):
        return None

    async def _fake_serialize_media(*_args, **_kwargs):
        return []

    async def _fake_available(*_args, **_kwargs):
        return True

    async def _fake_access(*_args, **_kwargs):
        return book, collaborator

    patch_route_dependency(monkeypatch, reader, "get_book_with_collaboration_access", _fake_access)
    patch_route_dependency(monkeypatch, reader, "consolidate_characters", _fake_consolidate)
    monkeypatch.setattr(
        reader, "backfill_character_first_chapters_for_chapter_text", _async_value(False)
    )
    patch_route_dependency(monkeypatch, reader, "chapter_intelligence_available", _fake_available)
    patch_route_dependency(monkeypatch, reader, "get_custom_tags_for_entity", _async_value([]))

    async def _fake_resolve_private(*_args, **_kwargs):
        return {
            "chapter_title": "Chapter 2",
            "content_version": 1,
            "text_url": "url:stored.json",
            "text_content": "private text",
            "html_content": "<p>private text</p>",
            "media": [],
            "analysis_status": None,
            "source_integrity": None,
        }

    patch_route_dependency(monkeypatch, reader, "resolve_reader_chapter_payload", _fake_resolve_private)

    payload = await reader.get_chapter(book.id, 2, db=db, current_user=_user(user_id))

    assert payload["can_copy_manuscript"] is False


@pytest.mark.asyncio
async def test_smart_tap_handles_processing_character_and_search_paths(monkeypatch):
    user_id = uuid.uuid4()
    book = _book(user_id=user_id)

    async def _fake_consolidate(*_args, **_kwargs):
        return None

    patch_route_dependency(monkeypatch, reader, "consolidate_characters", _fake_consolidate)

    db = _FakeDB(get_values=[book], scalar_values=[0])
    payload = await reader.smart_tap(
        book.id, q="iris", chapter=1, db=db, current_user=_user(user_id)
    )
    assert payload == {"type": "search", "results": []}

    char = SimpleNamespace(
        id=uuid.uuid4(),
        name="Iris",
        aliases=[],
        role="mc",
        trait_state={"eyes": "blue"},
        archetype="hero",
        personality_tags=[],
        motivations=[],
        fears=[],
        arc_summary="steady",
        first_chapter=1,
    )
    state = SimpleNamespace(
        at_chapter=2, trait_snapshot={"eyes": "green"}, arc_note="Recovering", prompt_delta=None
    )
    rel = SimpleNamespace(
        character_a_id=char.id,
        character_b_id=uuid.uuid4(),
        rel_type="ally",
        sentiment=0.8,
        description="Trusted",
    )
    db = _FakeDB(
        get_values=[book],
        scalar_values=[1],
        execute_values=[
            _Result(scalars=[char]),
            _Result(scalars=[state]),
            _Result(scalar=state),
            _Result(scalars=[rel]),
            _Result(scalars=[]),
        ],
    )
    monkeypatch.setattr(
        reader,
        "serialize_reader_character",
        lambda char, trait_snapshot=None, **_kwargs: {
            "id": str(char.id),
            "name": char.name,
            "aliases": [],
            "role": char.role,
            "first_chapter": char.first_chapter,
            "description": f"{char.archetype}:{trait_snapshot['eyes']}",
            "trait_state": trait_snapshot or {},
            "personality_tags": char.personality_tags or [],
            "motivations": char.motivations or [],
            "fears": char.fears or [],
            "archetype": char.archetype,
            "arc_summary": char.arc_summary,
            "mention_count": 0,
            "is_manual": False,
            "analysis_metadata": {"confidence_band": "medium"},
        },
    )
    payload = await reader.smart_tap(
        book.id, q="Iris", chapter=2, db=db, current_user=_user(user_id)
    )
    assert payload["type"] == "character"
    assert payload["character"]["description"] == "hero:green"
    assert payload["character"]["analysis_metadata"]["confidence_band"] == "medium"

    db = _FakeDB(
        get_values=[book],
        scalar_values=[1],
        execute_values=[_Result(scalar=None), _Result(all_rows=[("lexical match", 4, 2, "Storm")])],
    )

    async def _fake_context(*_args, **_kwargs):
        return []

    patch_route_dependency(monkeypatch, reader, "find_context_for_tap", _fake_context)
    patch_route_dependency(monkeypatch, reader, "build_search_result", lambda **kwargs: kwargs)
    payload = await reader.smart_tap(
        book.id, q="storm", chapter=2, db=db, current_user=_user(user_id)
    )
    assert payload["results"][0]["chapter_num"] == 2


@pytest.mark.asyncio
async def test_get_summary_handles_permissions_queue_and_success(monkeypatch):
    user_id = uuid.uuid4()
    book = _book(user_id=user_id)

    async def _fake_require_summary_access(*_args, **_kwargs):
        return None

    async def _fake_read_set(*_args, **_kwargs):
        return {2}

    async def _fake_queue(*_args, **_kwargs):
        return None

    patch_route_dependency(monkeypatch, reader, "summary_mode_allowed", lambda *_args: True)
    patch_route_dependency(monkeypatch, reader, "require_summary_access", _fake_require_summary_access)
    patch_route_dependency(monkeypatch, reader, "read_chapter_set", _fake_read_set)
    patch_route_dependency(monkeypatch, reader, "is_local_mode", lambda: False)
    patch_route_dependency(monkeypatch, reader, "queue_analysis_if_missing", _fake_queue)

    async def _fake_cache_set(*_args, **_kwargs):
        return None

    patch_route_dependency(monkeypatch, reader, "cache_set", _fake_cache_set)
    monkeypatch.setattr(
        reader, "normalize_summary_response", lambda content, *_args: {"content": content}
    )

    db = _FakeDB(get_values=[book])
    with pytest.raises(HTTPException) as exc:
        await reader.get_summary(book.id, 2, mode="bad", db=db, current_user=_user(user_id), _=None)
    assert exc.value.status_code == 400

    db = _FakeDB(
        get_values=[book], execute_values=[_Result(scalar=SimpleNamespace(id=uuid.uuid4()))]
    )

    async def _fake_no_summary(*_args, **_kwargs):
        return {"status": "pending", "content": None, "diagnostics": {"analysis_status": "queued"}}

    patch_route_dependency(monkeypatch, reader, "get_or_generate_summary", _fake_no_summary)
    payload = await reader.get_summary(
        book.id, 2, mode="short", db=db, current_user=_user(user_id), _=None
    )
    assert payload["status"] == "pending"
    assert payload["content"] is None

    chapter = SimpleNamespace(id=uuid.uuid4())
    db = _FakeDB(get_values=[book], execute_values=[_Result(scalar=chapter)])

    async def _fake_summary(*_args, **_kwargs):
        return {
            "status": "ready",
            "content": "Summary",
            "key_events": [],
            "char_changes": [],
            "clues": [],
            "diagnostics": {},
        }

    patch_route_dependency(monkeypatch, reader, "get_or_generate_summary", _fake_summary)
    payload = await reader.get_summary(
        book.id, 2, mode="short", db=db, current_user=_user(user_id), _=None
    )
    assert payload["status"] == "ready"
    assert payload["content"] == "Summary"


@pytest.mark.asyncio
async def test_reader_collection_routes_cover_events_relationships_search_and_chapter_lists(
    monkeypatch,
):
    user_id = uuid.uuid4()
    book = _book(user_id=user_id, mode="author")
    progress = SimpleNamespace(current_chapter=3, chapters_read=[1, 3])
    character = SimpleNamespace(
        id=uuid.uuid4(),
        name="Iris",
        role="mc",
        first_chapter=1,
        mention_count=4,
        aliases=[],
        motivations=[],
        fears=[],
        archetype="hero",
        arc_summary="arc",
        trait_state={"eyes": "blue"},
        personality_tags=[],
        growth_events=[{"chapter_number": 2, "event": "Learns truth"}],
    )
    rel = SimpleNamespace(
        id=uuid.uuid4(),
        character_a_id=character.id,
        character_b_id=uuid.uuid4(),
        rel_type="ally",
        sentiment=0.6,
        description="Works together",
        from_chapter=2,
        to_chapter=None,
    )
    chapter = SimpleNamespace(
        id=uuid.uuid4(), number=1, title="One", processed=False, content_version=1
    )

    async def _fake_cache_get(_key):
        return None

    async def _fake_cache_set(*_args, **_kwargs):
        return None

    async def _fake_consolidate(*_args, **_kwargs):
        return None

    patch_route_dependency(monkeypatch, reader, "cache_get", _fake_cache_get)
    patch_route_dependency(monkeypatch, reader, "cache_set", _fake_cache_set)
    patch_route_dependency(monkeypatch, reader, "consolidate_characters", _fake_consolidate)
    patch_route_dependency(monkeypatch, reader, "is_graph_character_visible", lambda _char: True)
    monkeypatch.setattr(
        reader,
        "collapse_graph_characters",
        lambda chars: (chars, {str(chars[0].id): str(chars[0].id)}),
    )
    patch_route_dependency(monkeypatch, reader, "relationship_node_description", lambda c, *_args: c.name)

    async def _fake_semantic_search(*_args, **_kwargs):
        return []

    patch_route_dependency(monkeypatch, reader, "semantic_search", _fake_semantic_search)
    patch_route_dependency(monkeypatch, reader, "build_search_result", lambda **kwargs: kwargs)

    async def _fake_int_map(*_args, **_kwargs):
        return {1: True}

    patch_route_dependency(monkeypatch, reader, "chapter_intelligence_map", _fake_int_map)
    monkeypatch.setattr("app.utils.reader_utils.chapter_intelligence_map", _fake_int_map)

    async def _fake_summary_visible(*_args, **_kwargs):
        return {1}

    patch_route_dependency(monkeypatch, reader, "summary_visible_chapter_set", _fake_summary_visible)
    monkeypatch.setattr("app.utils.reader_utils.summary_visible_chapter_set", _fake_summary_visible)
    patch_route_dependency(monkeypatch, reader, "list_custom_tags_for_entity_ids", _async_value({}))
    monkeypatch.setattr("app.utils.reader_utils.list_custom_tags_for_entity_ids", _async_value({}))

    async def _fake_queue(*_args, **_kwargs):
        return None

    async def _cache_version(*_args, **_kwargs):
        return 0

    async def _cache_miss(*_args, **_kwargs):
        return None

    async def _cache_write(*_args, **_kwargs):
        return None

    patch_route_dependency(monkeypatch, reader, "queue_analysis_if_missing", _fake_queue)
    monkeypatch.setattr("app.utils.reader_utils.queue_analysis_if_missing", _fake_queue)
    patch_route_dependency(monkeypatch, reader, "get_book_cache_version", _cache_version)
    patch_route_dependency(monkeypatch, reader, "get_reader_progress_cache_version", _cache_version)
    patch_route_dependency(monkeypatch, reader, "get_reader_events_cache", _cache_miss)
    patch_route_dependency(monkeypatch, reader, "set_reader_events_cache", _cache_write)

    async def _fake_short_summary(*_args, **_kwargs):
        return {"status": "ready", "content": "Generated", "key_events": [], "diagnostics": {}}

    patch_route_dependency(monkeypatch, reader, "get_or_generate_summary", _fake_short_summary)

    db = _FakeDB(
        get_values=[book, book, book, book, book],
        execute_values=[
            _Result(scalar=progress),
            _Result(all_rows=[(2, "Storm", [{"event": "Key Falls"}])]),
            _Result(scalars=[character]),
            _Result(scalars=[character]),
            _Result(scalars=[rel]),
            _Result(scalars=[]),
            _Result(all_rows=[("Storm clue", 2, 3, "Storm")]),
            _Result(scalar=progress),
            _Result(scalars=[chapter]),
            _Result(scalar=progress),
            _Result(scalars=[chapter]),
            _Result(all_rows=[(chapter.id, "Generated", [])]),
        ],
    )

    events = await reader.get_reader_events(
        book.id, chapter=None, db=db, current_user=_user(user_id)
    )
    relationships = await reader.get_relationships(
        book.id, chapter=3, db=db, current_user=_user(user_id)
    )
    search = await reader.search(
        book.id, q="storm clue", chapter=3, db=db, current_user=_user(user_id), _=None
    )
    chapters = await reader.get_chapter_list(book.id, db=db, current_user=_user(user_id))
    summaries = await reader.get_summary_collection(book.id, db=db, current_user=_user(user_id))

    assert events["items"][0]["event_title"] == "Key Falls"
    assert relationships["nodes"][0]["name"] == "Iris"
    assert search[0]["chapter_num"] == 3
    assert chapters["chapters"][0]["read"] is True
    assert summaries["summaries"][0]["available"] is True
    assert summaries["summaries"][0]["status"] == "ready"


@pytest.mark.asyncio
async def test_get_relationships_returns_hidden_nodes_and_inactive_edges_for_author_review(
    monkeypatch,
):
    user_id = uuid.uuid4()
    book = _book(user_id=user_id, mode="author")
    iris = SimpleNamespace(
        id=uuid.uuid4(),
        name="Iris",
        first_chapter=1,
        role="mc",
        aliases=[],
        arc_summary="Lead",
        mention_count=4,
        personality_tags=[],
        motivations=[],
        fears=[],
        archetype=None,
        trait_state={},
        is_manual=False,
    )
    sol = SimpleNamespace(
        id=uuid.uuid4(),
        name="Sol",
        first_chapter=1,
        role="sc",
        aliases=[],
        arc_summary="Friend",
        mention_count=3,
        personality_tags=[],
        motivations=[],
        fears=[],
        archetype=None,
        trait_state={},
        is_manual=False,
    )
    murmur = SimpleNamespace(
        id=uuid.uuid4(),
        name="Murmur",
        first_chapter=2,
        role=None,
        aliases=[],
        arc_summary=None,
        mention_count=1,
        personality_tags=[],
        motivations=[],
        fears=[],
        archetype=None,
        trait_state={},
        is_manual=False,
    )
    rel = SimpleNamespace(
        id=uuid.uuid4(),
        character_a_id=iris.id,
        character_b_id=sol.id,
        rel_type="ally",
        sentiment=0.6,
        description="Trusted",
        from_chapter=1,
        to_chapter=2,
    )

    async def _fake_consolidate(*_args, **_kwargs):
        return None

    async def _fake_cache_get(*_args, **_kwargs):
        return None

    async def _fake_cache_set(*_args, **_kwargs):
        return None

    patch_route_dependency(monkeypatch, reader, "consolidate_characters", _fake_consolidate)
    patch_route_dependency(monkeypatch, reader, "cache_get", _fake_cache_get)
    patch_route_dependency(monkeypatch, reader, "cache_set", _fake_cache_set)
    monkeypatch.setattr(
        reader,
        "collapse_graph_characters",
        lambda chars: (chars, {str(char.id): str(char.id) for char in chars}),
    )
    patch_route_dependency(monkeypatch, reader, "relationship_node_description", lambda c, *_args: c.name)
    patch_route_dependency(monkeypatch, reader, "is_graph_character_visible", lambda char: char.name != "Murmur")
    monkeypatch.setattr(
        reader,
        "graph_character_visibility_analysis",
        lambda char, _count=0: {
            "visible": char.name != "Murmur",
            "score": 4 if char.name != "Murmur" else 0,
            "override": None,
            "reasons": ["score_meets_threshold"]
            if char.name != "Murmur"
            else ["score_below_threshold"],
        },
    )

    db = _FakeDB(
        get_values=[book],
        execute_values=[
            _Result(scalars=[iris, sol, murmur]),
            _Result(scalars=[rel]),
            _Result(scalars=[]),
        ],
    )

    relationships = await reader.get_relationships(
        book.id, chapter=5, include_inactive=True, db=db, current_user=_user(user_id)
    )

    assert [node["name"] for node in relationships["nodes"]] == ["Iris", "Sol"]
    assert relationships["hidden_nodes"][0]["name"] == "Murmur"
    assert relationships["edges"][0]["status"] == "ended"


@pytest.mark.asyncio
async def test_get_relationships_collapses_reversed_duplicate_pair_rows(monkeypatch):
    user_id = uuid.uuid4()
    book = _book(user_id=user_id, mode="author")
    iris = SimpleNamespace(
        id=uuid.uuid4(),
        name="Iris",
        first_chapter=1,
        role="mc",
        aliases=[],
        arc_summary="Lead",
        mention_count=4,
        personality_tags=[],
        motivations=[],
        fears=[],
        archetype=None,
        trait_state={},
        is_manual=False,
    )
    sol = SimpleNamespace(
        id=uuid.uuid4(),
        name="Sol",
        first_chapter=1,
        role="sc",
        aliases=[],
        arc_summary="Friend",
        mention_count=3,
        personality_tags=[],
        motivations=[],
        fears=[],
        archetype=None,
        trait_state={},
        is_manual=False,
    )
    rel_one = SimpleNamespace(
        id=uuid.uuid4(),
        character_a_id=iris.id,
        character_b_id=sol.id,
        rel_type="ally",
        sentiment=0.6,
        description="Trusted",
        from_chapter=1,
        to_chapter=None,
    )
    rel_two = SimpleNamespace(
        id=uuid.uuid4(),
        character_a_id=sol.id,
        character_b_id=iris.id,
        rel_type="ally",
        sentiment=0.6,
        description="Trusted",
        from_chapter=3,
        to_chapter=None,
    )

    patch_route_dependency(monkeypatch, reader, "cache_get", _async_value(None))
    patch_route_dependency(monkeypatch, reader, "cache_set", _async_value(None))
    monkeypatch.setattr(
        reader,
        "collapse_graph_characters",
        lambda chars: (chars, {str(char.id): str(char.id) for char in chars}),
    )
    patch_route_dependency(monkeypatch, reader, "relationship_node_description", lambda c, *_args: c.name)
    patch_route_dependency(monkeypatch, reader, "is_graph_character_visible", lambda _char: True)
    monkeypatch.setattr(
        reader,
        "graph_character_visibility_analysis",
        lambda _char, _count=0: {
            "visible": True,
            "score": 4,
            "override": None,
            "reasons": ["score_meets_threshold"],
        },
    )

    db = _FakeDB(
        get_values=[book],
        execute_values=[
            _Result(scalars=[iris, sol]),
            _Result(scalars=[rel_one, rel_two]),
            _Result(scalars=[]),
        ],
    )

    relationships = await reader.get_relationships(
        book.id, chapter=5, db=db, current_user=_user(user_id)
    )

    assert len(relationships["edges"]) == 1
    assert relationships["edges"][0]["from_chapter"] == 1


@pytest.mark.asyncio
async def test_relationship_evolution_groups_reversed_pairs_into_one_timeline(monkeypatch):
    user_id = uuid.uuid4()
    book = _book(user_id=user_id)
    iris = SimpleNamespace(id=uuid.uuid4(), name="Iris")
    sol = SimpleNamespace(id=uuid.uuid4(), name="Sol")
    rel_one = SimpleNamespace(
        id=uuid.uuid4(),
        character_a_id=iris.id,
        character_b_id=sol.id,
        rel_type="enemy",
        sentiment=-0.6,
        description="Hostile",
        from_chapter=2,
        to_chapter=2,
        shared_labels=["rival"],
        character_a_to_b_labels=[],
        character_b_to_a_labels=[],
        label_evidence={"quote": "Hostile"},
    )
    rel_two = SimpleNamespace(
        id=uuid.uuid4(),
        character_a_id=sol.id,
        character_b_id=iris.id,
        rel_type="ally",
        sentiment=0.7,
        description="Trust",
        from_chapter=3,
        to_chapter=None,
        shared_labels=["friend_romantic"],
        character_a_to_b_labels=["protector"],
        character_b_to_a_labels=[],
        label_evidence={"quote": "Trust"},
    )

    patch_route_dependency(monkeypatch, reader, "get_book_cache_version", _async_value(1))
    patch_route_dependency(monkeypatch, reader, "get_reader_progress_cache_version", _async_value(1))
    patch_route_dependency(monkeypatch, reader, "get_relationship_evolution_cache", _async_value(None))
    patch_route_dependency(monkeypatch, reader, "set_relationship_evolution_cache", _async_value(None))

    db = _FakeDB(
        get_values=[book],
        execute_values=[
            _Result(scalars=[rel_one, rel_two]),
            _Result(scalars=[iris, sol]),
        ],
    )

    payload = await reader.get_relationship_evolution(
        book.id, chapter=5, db=db, current_user=_user(user_id)
    )

    assert len(payload["pairs"]) == 1
    assert payload["pairs"][0]["characters"] == ["Iris", "Sol"]
    assert [event["type"] for event in payload["pairs"][0]["events"]] == [
        "enemy",
        "friend_romantic",
    ]
    assert payload["pairs"][0]["events"][1]["shared_labels"] == ["friend_romantic"]


@pytest.mark.asyncio
async def test_reader_highlight_timeline_and_thematic_routes(monkeypatch):
    user_id = uuid.uuid4()
    char_id = uuid.uuid4()
    book = _book(user_id=user_id)

    async def _fake_summary_visible(*_args, **_kwargs):
        return {1, 2}

    async def _fake_timeline_visible(*_args, **_kwargs):
        return {1, 2}

    async def _fake_queue(*_args, **_kwargs):
        return None

    async def _cache_version(*_args, **_kwargs):
        return 0

    async def _cache_miss(*_args, **_kwargs):
        return None

    async def _cache_write(*_args, **_kwargs):
        return None

    patch_route_dependency(monkeypatch, reader, "summary_visible_chapter_set", _fake_summary_visible)
    patch_route_dependency(monkeypatch, reader, "timeline_visible_chapter_set", _fake_timeline_visible)
    patch_route_dependency(monkeypatch, reader, "queue_analysis_if_missing", _fake_queue)
    patch_route_dependency(monkeypatch, reader, "get_book_cache_version", _cache_version)
    patch_route_dependency(monkeypatch, reader, "get_reader_progress_cache_version", _cache_version)
    patch_route_dependency(monkeypatch, reader, "get_reader_timeline_cache", _cache_miss)
    patch_route_dependency(monkeypatch, reader, "set_reader_timeline_cache", _cache_write)
    monkeypatch.setattr(
        reader,
        "build_timeline_track_payload",
        lambda chapters, events, character_tracks, thread_tracks, relationship_markers: {
            "chapters": chapters,
            "events": events,
            "character_tracks": character_tracks,
            "thread_tracks": thread_tracks,
            "relationship_markers": relationship_markers,
        },
    )
    patch_route_dependency(monkeypatch, reader, "is_valid_timeline_character", lambda *_args: True)
    patch_route_dependency(monkeypatch, reader, "timeline_character_detail", lambda name, *_args: f"detail:{name}")
    monkeypatch.setattr(
        reader,
        "timeline_plot_thread_span",
        lambda introduced, resolved, _read_set: (introduced, resolved or 2) if introduced else None,
    )
    monkeypatch.setattr(
        reader, "timeline_relationship_detail", lambda a, b, *_args: (f"{a}/{b}", "shift")
    )
    patch_route_dependency(monkeypatch, reader, "dedupe_timeline_events", lambda items: items)
    patch_route_dependency(monkeypatch, reader, "download_book", lambda _key: b"storm signal text")

    rel = SimpleNamespace(
        id=uuid.uuid4(),
        character_a_id=char_id,
        character_b_id=uuid.uuid4(),
        rel_type="ally",
        description="Helps",
        from_chapter=2,
    )
    character = SimpleNamespace(
        id=char_id,
        name="Iris",
        first_chapter=1,
        role="mc",
        aliases=[],
        arc_summary="arc",
        last_seen_chapter=2,
    )
    db = _FakeDB(
        get_values=[book, book, book],
        execute_values=[
            _Result(all_rows=[(2, "Two", [{"clue": "Signal", "foreshadows": "Door"}])]),
            _Result(all_rows=[(1, "One", [{"event": "Start"}]), (2, "Two", [{"event": "Shift"}])]),
            _Result(all_rows=[("Iris", 1, "mc", [], "arc")]),
            _Result(all_rows=[(1, "One"), (2, "Two")]),
            _Result(all_rows=[(uuid.uuid4(), "Door", 1, 2, 2, "ongoing", None, "mystery")]),
            _Result(all_rows=[(rel, "Iris", "mc")]),
            _Result(scalars=[character]),
            _Result(scalars=[character]),
            _Result(
                all_rows=[(1, "One", "storm signal", [{"event": "signal"}], [{"clue": "Signal"}])]
            ),
        ],
    )

    highlights = await reader.get_foreshadowing_highlights(
        book.id, db=db, current_user=_user(user_id)
    )
    timeline = await reader.get_timeline(book.id, db=db, current_user=_user(user_id))
    thematic = await reader.thematic_search(
        book.id, q="signal", db=db, current_user=_user(user_id), _=None
    )

    assert highlights["items"][0]["clue"] == "Signal"
    assert timeline["chapters"][0]["number"] == 1
    assert thematic["results"][0]["chapter_number"] == 1


@pytest.mark.asyncio
async def test_reader_crud_progress_and_recall_routes(monkeypatch):
    user_id = uuid.uuid4()
    book = _book(user_id=user_id, total_chapters=4)
    progress = SimpleNamespace(current_chapter=2, scroll_pct=0.5, chapters_read=[], last_read=None)
    chapter = SimpleNamespace(
        id=uuid.uuid4(), number=2, processed=False, current_chapter=0, chapters_read=[]
    )
    quote_db = _FakeDB(get_values=[book])
    with pytest.raises(HTTPException):
        await reader.save_quote(
            book.id, SaveQuoteBody(quote_text=" "), db=quote_db, current_user=_user(user_id)
        )

    quote_db = _FakeDB(get_values=[book])
    payload = await reader.save_quote(
        book.id,
        SaveQuoteBody(
            quote_text="  Hello  ", chapter_number=2, character_name=" Iris ", note=" note "
        ),
        db=quote_db,
        current_user=_user(user_id),
    )
    assert payload["saved"] is True

    async def _fake_cache_get(_key):
        return None

    async def _fake_cache_set(*_args, **_kwargs):
        return None

    generated = {}

    async def _fake_generate_recall(**kwargs):
        generated.update(kwargs)
        return "Recall text"

    patch_route_dependency(monkeypatch, reader, "cache_get", _fake_cache_get)
    patch_route_dependency(monkeypatch, reader, "cache_set", _fake_cache_set)
    patch_route_dependency(monkeypatch, reader, "generate_recall", _fake_generate_recall)
    dirty_calls = []

    async def _mark_progress_dirty(book_id, user_id):
        dirty_calls.append((book_id, user_id))
        return 1

    patch_route_dependency(monkeypatch, reader, "mark_reader_progress_cache_dirty", _mark_progress_dirty)
    db = _FakeDB(
        get_values=[book, book, book, book, book, book, book],
        execute_values=[
            _Result(scalar=None),
            _Result(scalar=progress),
            _Result(scalar=chapter),
            _Result(scalar=SimpleNamespace(content="Summary")),
            _Result(scalars=["Iris"]),
            _Result(scalars=["Door"]),
            _Result(scalar=progress),
            _Result(scalar=progress),
            _Result(
                scalar=SimpleNamespace(
                    id=uuid.uuid4(), processed=False, current_chapter=0, chapters_read=[]
                )
            ),
            _Result(scalar=chapter),
            _Result(scalar=None),
            _Result(scalar=chapter),
            _Result(scalar=progress),
            _Result(scalar=chapter),
        ],
    )
    patch_route_dependency(monkeypatch, reader, "key_memory_recall", lambda *_args: "recall-key")
    patch_route_dependency(monkeypatch, reader, "queue_for_user", lambda *_args: "extraction")

    async def _fake_available(*_args, **_kwargs):
        return True

    patch_route_dependency(monkeypatch, reader, "chapter_intelligence_available", _fake_available)

    async def _fake_queue(*_args, **_kwargs):
        return None

    patch_route_dependency(monkeypatch, reader, "queue_analysis_if_missing", _fake_queue)

    async def _fake_sync_beta_assignments(*_args, **_kwargs):
        return None

    monkeypatch.setattr(
        reader, "sync_beta_assignments_for_reader_book", _fake_sync_beta_assignments
    )
    task_calls = []
    monkeypatch.setattr(
        __import__("app.workers.tasks.extraction_tasks", fromlist=["process_chapter_task"]),
        "process_chapter_task",
        SimpleNamespace(apply_async=lambda **kwargs: task_calls.append(kwargs)),
    )

    no_progress = await reader.memory_recall(book.id, db=db, current_user=_user(user_id))
    recall = await reader.memory_recall(book.id, db=db, current_user=_user(user_id))
    progress_payload = await reader.get_progress(book.id, db=db, current_user=_user(user_id))
    updated = await reader.update_progress(
        book.id, current_chapter=2, scroll_pct=0.8, db=db, current_user=_user(user_id)
    )
    marked = await reader.mark_book_read(book.id, db=db, current_user=_user(user_id))
    status = await reader.update_chapter_read_status(
        book.id, chapter=3, read=True, db=db, current_user=_user(user_id)
    )

    assert no_progress == {"recall": None}
    assert recall["recall"] == "Recall text"
    assert generated["usage_db"] is None
    assert db.rollbacks == 1
    assert db.commits == 3
    assert progress_payload["chapters_read_count"] == 2
    assert updated == {"ok": True}
    assert marked["percent_complete"] == 100.0
    assert status["read"] is True
    assert task_calls == []
    assert len(dirty_calls) == 3


@pytest.mark.asyncio
async def test_memory_recall_caches_book_title_before_rollback(monkeypatch):
    user_id = uuid.uuid4()
    book_id = uuid.uuid4()
    progress = SimpleNamespace(current_chapter=2, scroll_pct=0.5, chapters_read=[], last_read=None)
    chapter = SimpleNamespace(id=uuid.uuid4(), number=2, processed=False)
    db = _FakeDB(
        get_values=[],
        execute_values=[
            _Result(scalar=progress),
            _Result(scalar=chapter),
            _Result(scalar=SimpleNamespace(content="Summary")),
            _Result(scalars=["Iris"]),
            _Result(all_rows=[]),
        ],
    )
    book = _RollbackSensitiveBook(book_id=book_id, user_id=user_id, db=db)
    db._get_values = [book]

    async def _fake_cache_get(_key):
        return None

    async def _fake_cache_set(*_args, **_kwargs):
        return None

    generated = {}

    async def _fake_generate_recall(**kwargs):
        generated.update(kwargs)
        return "Recall text"

    patch_route_dependency(monkeypatch, reader, "cache_get", _fake_cache_get)
    patch_route_dependency(monkeypatch, reader, "cache_set", _fake_cache_set)
    patch_route_dependency(monkeypatch, reader, "generate_recall", _fake_generate_recall)
    patch_route_dependency(monkeypatch, reader, "key_memory_recall", lambda *_args: "recall-key")

    payload = await reader.memory_recall(book_id, db=db, current_user=_user(user_id))

    assert payload["recall"] == "Recall text"
    assert generated["title"] == "Atlas"
    assert generated["usage_db"] is None
    assert db.rollbacks == 1


@pytest.mark.asyncio
async def test_plot_thread_routes_and_relationship_evolution(monkeypatch):
    user_id = uuid.uuid4()
    book = _book(user_id=user_id)
    pair_a = uuid.uuid4()
    pair_b = uuid.uuid4()
    rel = SimpleNamespace(
        character_a_id=pair_a,
        character_b_id=pair_b,
        from_chapter=2,
        rel_type="ally",
        description="Bonds",
        sentiment=0.4,
    )
    db = _FakeDB(
        get_values=[book, book, book, book],
        execute_values=[
            _Result(scalars=[rel]),
            _Result(
                scalars=[
                    SimpleNamespace(id=pair_a, name="Iris"),
                    SimpleNamespace(id=pair_b, name="Milo"),
                ]
            ),
        ],
    )

    async def _fake_list_threads(*_args, **_kwargs):
        return [
            {"id": "1", "title": "Door", "status": "ongoing", "importance": 8, "character_ids": []}
        ]

    async def _fake_update(*_args, **_kwargs):
        return {
            "id": "1",
            "title": "Door",
            "status": "paused",
            "importance": 8,
            "character_ids": [],
            "related_characters": [],
            "mention_count": 2,
            "note": "Updated",
        }

    async def _cache_version(*_args, **_kwargs):
        return 0

    async def _cache_miss(*_args, **_kwargs):
        return None

    async def _cache_write(*_args, **_kwargs):
        return None

    patch_route_dependency(monkeypatch, reader, "list_plot_threads", _fake_list_threads)
    patch_route_dependency(monkeypatch, reader, "update_plot_thread_note", _fake_update)
    patch_route_dependency(monkeypatch, reader, "get_book_cache_version", _cache_version)
    patch_route_dependency(monkeypatch, reader, "get_reader_progress_cache_version", _cache_version)
    patch_route_dependency(monkeypatch, reader, "get_relationship_evolution_cache", _cache_miss)
    patch_route_dependency(monkeypatch, reader, "set_relationship_evolution_cache", _cache_write)

    evolution = await reader.get_relationship_evolution(
        book.id, chapter=3, db=db, current_user=_user(user_id)
    )
    threads = await reader.get_plot_threads(book.id, chapter=3, db=db, current_user=_user(user_id))
    updated = await reader.save_plot_thread_note(
        book.id,
        uuid.uuid4(),
        UpdatePlotThreadBody(note="Updated", status="paused"),
        db=db,
        current_user=_user(user_id),
    )

    assert evolution["pairs"][0]["characters"] == ["Iris", "Milo"]
    assert threads[0]["title"] == "Door"
    assert updated["note"] == "Updated"
    assert updated["status"] == "paused"


@pytest.mark.asyncio
async def test_reader_events_timeline_and_relationship_evolution_return_cached_payloads(
    monkeypatch,
):
    user_id = uuid.uuid4()
    book = _book(user_id=user_id)
    major_payload = {
        "major_events": [
            {
                "chapter_number": 2,
                "chapter_title": "Storm",
                "event_title": "Key Falls",
                "description": "desc",
                "importance": 5,
                "involved_characters": None,
                "involved_character_names": None,
                "event_type": None,
            }
        ],
        "character_events": [],
    }
    timeline_payload = {
        "chapters": [{"number": 1, "title": "One"}],
        "events": [],
        "character_tracks": [],
        "thread_tracks": [],
        "relationship_markers": [],
    }
    evolution_payload = {
        "pairs": [
            {
                "characters": ["Iris", "Milo"],
                "events": [
                    {"chapter": 2, "type": "ally", "description": "Bonds", "sentiment": 0.4}
                ],
            }
        ]
    }

    async def _cache_version(*_args, **_kwargs):
        return 7

    patch_route_dependency(monkeypatch, reader, "get_book_cache_version", _cache_version)
    patch_route_dependency(monkeypatch, reader, "get_reader_progress_cache_version", _cache_version)
    patch_route_dependency(monkeypatch, reader, "get_reader_events_cache", _async_value(major_payload))
    patch_route_dependency(monkeypatch, reader, "get_reader_timeline_cache", _async_value(timeline_payload))
    patch_route_dependency(monkeypatch, reader, "get_relationship_evolution_cache", _async_value(evolution_payload))

    events = await reader.get_reader_events(
        book.id,
        chapter=2,
        db=_FakeDB(get_values=[book], execute_values=[_Result(scalar=None)]),
        current_user=_user(user_id),
    )
    timeline = await reader.get_timeline(
        book.id, db=_FakeDB(get_values=[book]), current_user=_user(user_id)
    )
    evolution = await reader.get_relationship_evolution(
        book.id, chapter=2, db=_FakeDB(get_values=[book]), current_user=_user(user_id)
    )

    assert events["items"][0]["event_title"] == "Key Falls"
    assert timeline["chapters"][0]["title"] == "One"
    assert evolution["pairs"][0]["characters"] == ["Iris", "Milo"]


@pytest.mark.asyncio
async def test_get_chapter_validates_empty_project():
    """Test that get_chapter returns helpful error for empty projects."""
    user_id = uuid.uuid4()
    book = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=user_id,
        title="Empty Project",
        total_chapters=0,
        is_editor_project=True,
        mode="author",
        format="manual",
        is_public=False,
        is_truncated=False,
        total_tokens=0,
    )
    db = _FakeDB(get_values=[book])

    with pytest.raises(HTTPException) as exc_info:
        await reader.get_chapter(book.id, 1, db=db, current_user=_user(user_id))

    assert exc_info.value.status_code == 400
    assert "no chapters yet" in exc_info.value.detail.lower()
    assert "create your first chapter" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_get_chapter_validates_chapter_number_range(monkeypatch):
    """Test that get_chapter validates chapter number is within valid range."""
    user_id = uuid.uuid4()
    book = _book(user_id=user_id, total_chapters=5)

    async def _fake_access(*_args, **_kwargs):
        return book, None

    patch_route_dependency(monkeypatch, reader, "get_book_with_collaboration_access", _fake_access)
    db = _FakeDB()

    # Test chapter number too high
    with pytest.raises(HTTPException) as exc_info:
        await reader.get_chapter(book.id, 10, db=db, current_user=_user(user_id))

    assert exc_info.value.status_code == 404
    assert "does not exist" in exc_info.value.detail.lower()
    assert "5 chapters" in exc_info.value.detail.lower()

    # Test chapter number too low
    with pytest.raises(HTTPException) as exc_info:
        await reader.get_chapter(book.id, 0, db=db, current_user=_user(user_id))

    assert exc_info.value.status_code == 400
    assert "invalid chapter number" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_get_chapter_validates_none_total_chapters():
    """Test that get_chapter handles books with None total_chapters."""
    user_id = uuid.uuid4()
    book = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=user_id,
        title="Processing Book",
        total_chapters=None,
        is_editor_project=False,
        mode="reader",
        format="epub",
        is_public=False,
        is_truncated=False,
        total_tokens=0,
    )
    db = _FakeDB(get_values=[book])

    with pytest.raises(HTTPException) as exc_info:
        await reader.get_chapter(book.id, 1, db=db, current_user=_user(user_id))

    assert exc_info.value.status_code == 400
    assert "no chapters yet" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_get_summary_validates_chapter_range(monkeypatch):
    """Test that get_summary validates chapter number is within valid range."""
    user_id = uuid.uuid4()
    book = _book(user_id=user_id, total_chapters=3)

    async def _fake_access(*_args, **_kwargs):
        return book, None

    patch_route_dependency(monkeypatch, reader, "get_book_with_collaboration_access", _fake_access)
    patch_route_dependency(monkeypatch, reader, "summary_mode_allowed", lambda *a, **kw: True)
    db = _FakeDB()

    with pytest.raises(HTTPException) as exc_info:
        await reader.get_summary(book.id, 10, mode="short", db=db, current_user=_user(user_id))

    assert exc_info.value.status_code == 404
    assert "does not exist" in exc_info.value.detail.lower()
