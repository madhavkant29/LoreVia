from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1.routes import reader
from app.schemas.reader import SaveQuoteBody, UpdatePlotThreadBody


class _ScalarList:
    def __init__(self, items):
        self._items = items

    def all(self):
        return list(self._items)


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

    async def refresh(self, item):
        self.refreshed.append(item)


def _user(user_id: uuid.UUID):
    return SimpleNamespace(id=user_id, tier="reader")


def _book(*, user_id: uuid.UUID, total_chapters: int = 6, mode: str = "reader", fmt: str = "epub"):
    return SimpleNamespace(
        id=uuid.uuid4(),
        user_id=user_id,
        title="Atlas",
        total_chapters=total_chapters,
        mode=mode,
        format=fmt,
    )


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
    media = SimpleNamespace(id=media_id, book_id=uuid.uuid4(), storage_key="media.bin", content_type="image/png")
    book = SimpleNamespace(id=media.book_id, user_id=user_id)

    db = _FakeDB(get_values=[media, book])
    monkeypatch.setattr(reader, "decode_token", lambda _token: None)
    with pytest.raises(HTTPException) as exc:
        await reader.get_chapter_media_public(media_id, token="bad", db=db)
    assert exc.value.status_code == 401

    db = _FakeDB(get_values=[media, book])
    monkeypatch.setattr(
        reader,
        "decode_token",
        lambda _token: {"type": "asset", "sub": str(user_id), "res": f"chapter-media:{media_id}"},
    )
    monkeypatch.setattr(reader, "download_book", lambda _key: b"png")
    response = await reader.get_chapter_media_public(media_id, token="ok", db=db)
    assert response.media_type == "image/png"


@pytest.mark.asyncio
async def test_get_chapter_supports_fallback_and_stored_content(monkeypatch):
    user_id = uuid.uuid4()
    book = _book(user_id=user_id, total_chapters=8, fmt="pdf")
    db = _FakeDB(get_values=[book], execute_values=[_Result(scalar=None), _Result(scalars=[])])
    monkeypatch.setattr(reader, "consolidate_characters", lambda *_args, **_kwargs: None)
    async def _fake_consolidate(*_args, **_kwargs):
        return None
    monkeypatch.setattr(reader, "consolidate_characters", _fake_consolidate)
    monkeypatch.setattr(reader, "parse_chapter_from_source", lambda *_args: {"title": "Fallback", "text": "Fallback text", "images": [{"src": "a"}]})
    monkeypatch.setattr(reader, "serialize_inline_images", lambda images: [{"count": len(images)}])
    async def _fake_available(*_args, **_kwargs):
        return True
    monkeypatch.setattr(reader, "chapter_intelligence_available", _fake_available)

    payload = await reader.get_chapter(book.id, 2, db=db, current_user=_user(user_id))
    assert payload["chapter_title"] == "Fallback"
    assert payload["text_content"] == "Fallback text"

    chapter_id = uuid.uuid4()
    chapter = SimpleNamespace(id=chapter_id, book_id=book.id, number=2, title="Stored", s3_key="stored.json")
    character = SimpleNamespace(
        id=uuid.uuid4(),
        name="Iris",
        aliases=[],
        role="mc",
        first_chapter=1,
        archetype="hero",
        personality_tags=["brave"],
        trait_state={"eyes": "blue"},
    )
    state = SimpleNamespace(character_id=character.id, trait_snapshot={"eyes": "green"})
    db = _FakeDB(
        get_values=[book],
        execute_values=[_Result(scalar=chapter), _Result(scalars=[character]), _Result(scalars=[state])],
    )
    monkeypatch.setattr(reader, "download_book", lambda _key: b"payload")
    monkeypatch.setattr(reader, "deserialize_manuscript_content", lambda _raw: {"text": "[[IMAGE:1]] body", "html": "<p>body</p>"})
    async def _fake_serialize_media(*_args, **_kwargs):
        return []
    monkeypatch.setattr(reader, "serialize_chapter_media", _fake_serialize_media)
    monkeypatch.setattr(reader, "extract_media_markers", lambda text: [] if text else [])
    monkeypatch.setattr(reader, "parse_chapter_from_source", lambda *_args: {"title": "Recovered", "text": "[[IMAGE:1]] recovered", "images": [{"src": "b"}]})
    monkeypatch.setattr(reader, "serialize_inline_images", lambda images: [{"count": len(images)}])
    monkeypatch.setattr(reader, "merge_media_items", lambda stored, fallback: stored + fallback)
    monkeypatch.setattr(reader, "build_description", lambda traits, archetype: f"{archetype}:{traits['eyes']}")
    monkeypatch.setattr(reader, "get_presigned_url", lambda key: f"url:{key}")

    payload = await reader.get_chapter(book.id, 2, db=db, current_user=_user(user_id))
    assert payload["text_url"] == "url:stored.json"
    assert payload["chapter_title"] == "Stored"
    assert payload["characters"][0]["description"] == "hero:green"


@pytest.mark.asyncio
async def test_smart_tap_handles_processing_character_and_search_paths(monkeypatch):
    user_id = uuid.uuid4()
    book = _book(user_id=user_id)
    async def _fake_consolidate(*_args, **_kwargs):
        return None
    monkeypatch.setattr(reader, "consolidate_characters", _fake_consolidate)

    db = _FakeDB(get_values=[book], scalar_values=[0])
    payload = await reader.smart_tap(book.id, q="iris", chapter=1, db=db, current_user=_user(user_id))
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
        first_chapter=1,
    )
    state = SimpleNamespace(trait_snapshot={"eyes": "green"}, arc_note="Recovering")
    rel = SimpleNamespace(character_a_id=char.id, character_b_id=uuid.uuid4(), rel_type="ally", sentiment=0.8, description="Trusted")
    db = _FakeDB(
        get_values=[book],
        scalar_values=[1],
        execute_values=[_Result(scalar=char), _Result(scalar=state), _Result(scalars=[rel])],
    )
    monkeypatch.setattr(reader, "build_description", lambda traits, archetype: f"{archetype}:{traits['eyes']}")
    payload = await reader.smart_tap(book.id, q="Iris", chapter=2, db=db, current_user=_user(user_id))
    assert payload["type"] == "character"
    assert payload["character"]["description"] == "hero:green"

    db = _FakeDB(
        get_values=[book],
        scalar_values=[1],
        execute_values=[_Result(scalar=None), _Result(all_rows=[("lexical match", 4, 2, "Storm")])],
    )
    async def _fake_context(*_args, **_kwargs):
        return []
    monkeypatch.setattr(reader, "find_context_for_tap", _fake_context)
    monkeypatch.setattr(reader, "build_search_result", lambda **kwargs: kwargs)
    payload = await reader.smart_tap(book.id, q="storm", chapter=2, db=db, current_user=_user(user_id))
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

    monkeypatch.setattr(reader, "summary_mode_allowed", lambda *_args: True)
    monkeypatch.setattr(reader, "require_summary_access", _fake_require_summary_access)
    monkeypatch.setattr(reader, "read_chapter_set", _fake_read_set)
    monkeypatch.setattr(reader, "is_local_mode", lambda: False)
    monkeypatch.setattr(reader, "queue_analysis_if_missing", _fake_queue)
    async def _fake_cache_set(*_args, **_kwargs):
        return None
    monkeypatch.setattr(reader, "cache_set", _fake_cache_set)
    monkeypatch.setattr(reader, "normalize_summary_response", lambda content, *_args: {"content": content})

    db = _FakeDB(get_values=[book])
    with pytest.raises(HTTPException) as exc:
        await reader.get_summary(book.id, 2, mode="bad", db=db, current_user=_user(user_id), _=None)
    assert exc.value.status_code == 400

    db = _FakeDB(get_values=[book], execute_values=[_Result(scalar=SimpleNamespace(id=uuid.uuid4()))])
    async def _fake_no_summary(*_args, **_kwargs):
        return None
    monkeypatch.setattr(reader, "get_or_generate_summary", _fake_no_summary)
    with pytest.raises(HTTPException) as exc:
        await reader.get_summary(book.id, 2, mode="short", db=db, current_user=_user(user_id), _=None)
    assert exc.value.status_code == 503

    chapter = SimpleNamespace(id=uuid.uuid4())
    db = _FakeDB(get_values=[book], execute_values=[_Result(scalar=chapter)])
    async def _fake_summary(*_args, **_kwargs):
        return {"content": "Summary", "key_events": [], "char_changes": [], "clues": []}
    monkeypatch.setattr(reader, "get_or_generate_summary", _fake_summary)
    payload = await reader.get_summary(book.id, 2, mode="short", db=db, current_user=_user(user_id), _=None)
    assert payload["content"] == "Summary"


@pytest.mark.asyncio
async def test_reader_collection_routes_cover_events_relationships_search_and_chapter_lists(monkeypatch):
    user_id = uuid.uuid4()
    book = _book(user_id=user_id, mode="author")
    progress = SimpleNamespace(current_chapter=3, chapters_read=[1, 3])
    character = SimpleNamespace(
        id=uuid.uuid4(),
        name="Iris",
        role="mc",
        first_chapter=1,
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
    chapter = SimpleNamespace(id=uuid.uuid4(), number=1, title="One", processed=False)
    async def _fake_cache_get(_key):
        return None
    async def _fake_cache_set(*_args, **_kwargs):
        return None
    async def _fake_consolidate(*_args, **_kwargs):
        return None
    monkeypatch.setattr(reader, "cache_get", _fake_cache_get)
    monkeypatch.setattr(reader, "cache_set", _fake_cache_set)
    monkeypatch.setattr(reader, "consolidate_characters", _fake_consolidate)
    monkeypatch.setattr(reader, "is_graph_character_visible", lambda _char: True)
    monkeypatch.setattr(reader, "collapse_graph_characters", lambda chars: (chars, {str(chars[0].id): str(chars[0].id)}))
    monkeypatch.setattr(reader, "relationship_node_description", lambda c, *_args: c.name)
    async def _fake_semantic_search(*_args, **_kwargs):
        return []
    monkeypatch.setattr(reader, "semantic_search", _fake_semantic_search)
    monkeypatch.setattr(reader, "build_search_result", lambda **kwargs: kwargs)
    async def _fake_int_map(*_args, **_kwargs):
        return {1: True}
    monkeypatch.setattr(reader, "chapter_intelligence_map", _fake_int_map)
    async def _fake_summary_visible(*_args, **_kwargs):
        return {1}
    monkeypatch.setattr(reader, "summary_visible_chapter_set", _fake_summary_visible)
    async def _fake_queue(*_args, **_kwargs):
        return None
    monkeypatch.setattr(reader, "queue_analysis_if_missing", _fake_queue)
    async def _fake_short_summary(*_args, **_kwargs):
        return {"content": "Generated", "key_events": []}
    monkeypatch.setattr(reader, "get_or_generate_summary", _fake_short_summary)

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
            _Result(all_rows=[]),
        ],
    )

    events = await reader.get_reader_events(book.id, chapter=None, db=db, current_user=_user(user_id))
    relationships = await reader.get_relationships(book.id, chapter=3, db=db, current_user=_user(user_id))
    search = await reader.search(book.id, q="storm clue", chapter=3, db=db, current_user=_user(user_id), _=None)
    chapters = await reader.get_chapter_list(book.id, db=db, current_user=_user(user_id))
    summaries = await reader.get_summary_collection(book.id, db=db, current_user=_user(user_id))

    assert events.major_events[0].event_title == "Key Falls"
    assert relationships["nodes"][0]["name"] == "Iris"
    assert search[0]["chapter_num"] == 3
    assert chapters["chapters"][0]["read"] is True
    assert summaries["summaries"][0]["available"] is True


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

    monkeypatch.setattr(reader, "summary_visible_chapter_set", _fake_summary_visible)
    monkeypatch.setattr(reader, "timeline_visible_chapter_set", _fake_timeline_visible)
    monkeypatch.setattr(reader, "queue_analysis_if_missing", _fake_queue)
    monkeypatch.setattr(reader, "build_timeline_track_payload", lambda chapters, events, character_tracks, thread_tracks, relationship_markers: {"chapters": chapters, "events": events, "character_tracks": character_tracks, "thread_tracks": thread_tracks, "relationship_markers": relationship_markers})
    monkeypatch.setattr(reader, "is_valid_timeline_character", lambda *_args: True)
    monkeypatch.setattr(reader, "timeline_character_detail", lambda name, *_args: f"detail:{name}")
    monkeypatch.setattr(reader, "timeline_plot_thread_span", lambda introduced, resolved, _read_set: (introduced, resolved or 2) if introduced else None)
    monkeypatch.setattr(reader, "timeline_relationship_detail", lambda a, b, *_args: (f"{a}/{b}", "shift"))
    monkeypatch.setattr(reader, "dedupe_timeline_events", lambda items: items)
    monkeypatch.setattr(reader, "download_book", lambda _key: b"storm signal text")

    chapter = SimpleNamespace(id=uuid.uuid4(), number=2, title="Two", s3_key="two.txt")
    summary_row = SimpleNamespace(content="storm signal", clues=[{"clue": "Signal", "foreshadows": "Door"}])
    rel = SimpleNamespace(id=uuid.uuid4(), character_a_id=char_id, character_b_id=uuid.uuid4(), rel_type="ally", description="Helps", from_chapter=2)
    character = SimpleNamespace(id=char_id, name="Iris", first_chapter=1, role="mc", aliases=[], arc_summary="arc", last_seen_chapter=2)
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
            _Result(all_rows=[(1, "One", "storm signal", [{"event": "signal"}], [{"clue": "Signal"}])]),
        ],
    )

    highlights = await reader.get_foreshadowing_highlights(book.id, db=db, current_user=_user(user_id))
    timeline = await reader.get_timeline(book.id, db=db, current_user=_user(user_id))
    thematic = await reader.thematic_search(book.id, q="signal", db=db, current_user=_user(user_id), _=None)

    assert highlights["items"][0]["clue"] == "Signal"
    assert timeline["chapters"][0]["number"] == 1
    assert thematic["results"][0]["chapter_number"] == 1


@pytest.mark.asyncio
async def test_reader_crud_progress_and_recall_routes(monkeypatch):
    user_id = uuid.uuid4()
    book = _book(user_id=user_id, total_chapters=4)
    progress = SimpleNamespace(current_chapter=2, scroll_pct=0.5, chapters_read=[], last_read=None)
    chapter = SimpleNamespace(id=uuid.uuid4(), number=2, processed=False)
    quote_db = _FakeDB(get_values=[book])
    with pytest.raises(HTTPException):
        await reader.save_quote(book.id, SaveQuoteBody(quote_text=" "), db=quote_db, current_user=_user(user_id))

    quote_db = _FakeDB(get_values=[book])
    payload = await reader.save_quote(book.id, SaveQuoteBody(quote_text="  Hello  ", chapter_number=2, character_name=" Iris ", note=" note "), db=quote_db, current_user=_user(user_id))
    assert payload["saved"] is True

    async def _fake_cache_get(_key):
        return None
    async def _fake_cache_set(*_args, **_kwargs):
        return None
    async def _fake_generate_recall(**_kwargs):
        return "Recall text"
    monkeypatch.setattr(reader, "cache_get", _fake_cache_get)
    monkeypatch.setattr(reader, "cache_set", _fake_cache_set)
    monkeypatch.setattr(reader, "generate_recall", _fake_generate_recall)
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
            _Result(scalar=SimpleNamespace(id=uuid.uuid4(), processed=False)),
            _Result(scalar=chapter),
            _Result(scalar=None),
            _Result(scalar=chapter),
            _Result(scalar=progress),
            _Result(scalar=chapter),
        ],
    )
    monkeypatch.setattr(reader, "key_memory_recall", lambda *_args: "recall-key")
    monkeypatch.setattr(reader, "queue_for_user", lambda *_args: "extraction")
    async def _fake_available(*_args, **_kwargs):
        return True
    monkeypatch.setattr(reader, "chapter_intelligence_available", _fake_available)
    async def _fake_queue(*_args, **_kwargs):
        return None
    monkeypatch.setattr(reader, "queue_analysis_if_missing", _fake_queue)
    task_calls = []
    monkeypatch.setattr(
        __import__("app.workers.tasks.extraction_tasks", fromlist=["process_chapter_task"]),
        "process_chapter_task",
        SimpleNamespace(apply_async=lambda **kwargs: task_calls.append(kwargs)),
    )

    no_progress = await reader.memory_recall(book.id, db=db, current_user=_user(user_id))
    recall = await reader.memory_recall(book.id, db=db, current_user=_user(user_id))
    progress_payload = await reader.get_progress(book.id, db=db, current_user=_user(user_id))
    updated = await reader.update_progress(book.id, current_chapter=2, scroll_pct=0.8, db=db, current_user=_user(user_id))
    marked = await reader.mark_book_read(book.id, db=db, current_user=_user(user_id))
    status = await reader.update_chapter_read_status(book.id, chapter=3, read=True, db=db, current_user=_user(user_id))

    assert no_progress == {"recall": None}
    assert recall["recall"] == "Recall text"
    assert progress_payload["chapters_read_count"] == 2
    assert updated == {"ok": True}
    assert marked["percent_complete"] == 100.0
    assert status["read"] is True
    assert task_calls


@pytest.mark.asyncio
async def test_plot_thread_routes_and_relationship_evolution(monkeypatch):
    user_id = uuid.uuid4()
    book = _book(user_id=user_id)
    pair_a = uuid.uuid4()
    pair_b = uuid.uuid4()
    rel = SimpleNamespace(character_a_id=pair_a, character_b_id=pair_b, from_chapter=2, rel_type="ally", description="Bonds", sentiment=0.4)
    db = _FakeDB(
        get_values=[book, book, book, book],
        execute_values=[
            _Result(scalars=[rel]),
            _Result(scalars=[SimpleNamespace(id=pair_a, name="Iris"), SimpleNamespace(id=pair_b, name="Milo")]),
        ],
    )
    async def _fake_list_threads(*_args, **_kwargs):
        return [{"id": "1", "title": "Door", "status": "ongoing", "importance": 8, "character_ids": []}]
    async def _fake_update(*_args, **_kwargs):
        return {"id": "1", "title": "Door", "status": "paused", "importance": 8, "character_ids": [], "related_characters": [], "mention_count": 2, "note": "Updated"}
    monkeypatch.setattr(reader, "list_plot_threads", _fake_list_threads)
    monkeypatch.setattr(reader, "update_plot_thread_note", _fake_update)

    evolution = await reader.get_relationship_evolution(book.id, chapter=3, db=db, current_user=_user(user_id))
    threads = await reader.get_plot_threads(book.id, chapter=3, db=db, current_user=_user(user_id))
    updated = await reader.save_plot_thread_note(book.id, uuid.uuid4(), UpdatePlotThreadBody(note="Updated", status="paused"), db=db, current_user=_user(user_id))

    assert evolution["pairs"][0]["characters"] == ["Iris", "Milo"]
    assert threads[0]["title"] == "Door"
    assert updated["note"] == "Updated"
    assert updated["status"] == "paused"
