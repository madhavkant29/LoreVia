import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.exc import ProgrammingError

from app.models.book import Book, Series, SeriesBook
from app.models.character import Character
from app.models.intelligence import PlotThread
from app.models.user import User
from app.utils import advisor_chat_utils, advisor_utils
from app.utils.advisor_story_context_utils import build_series_story_context, build_story_context
from app.utils.advisor_utils import (
    advisor_retrieval_settings,
    build_advisor_world_context,
    build_fallback_advisor_suggestions,
    classify_intent_fast,
    classify_response_type,
    detect_advisor_world_mode,
    identify_character_mentions,
    invalidate_advisor_caches,
    invalidate_advisor_caches_for_book,
    language_context_hint,
    normalize_proactive_scan_result,
    retrieve_series_continuity_passages,
)


def test_build_fallback_advisor_suggestions_returns_three_items_without_focus_thread():
    suggestions = build_fallback_advisor_suggestions(
        book_title="Lord El Melloi",
        total_chapters=50,
        character_count=18,
        open_thread_count=4,
        focus_thread=None,
    )

    assert len(suggestions) == 3
    assert suggestions[0]["type"] == "manuscript_checkpoint"
    assert suggestions[-1]["type"] == "unresolved_clue"


def test_build_fallback_advisor_suggestions_uses_focus_thread_when_available():
    suggestions = build_fallback_advisor_suggestions(
        book_title="Lord El Melloi",
        total_chapters=50,
        character_count=18,
        open_thread_count=4,
        focus_thread={
            "title": "The sealed letter",
            "introduced_at": 8,
            "description": "Mentioned repeatedly but not resolved.",
        },
    )

    assert len(suggestions) == 3
    assert suggestions[-1]["type"] == "future_direction"
    assert "sealed letter" in suggestions[-1]["title"].lower()


def test_detect_advisor_world_mode_routes_gap_questions_to_gap_detection():
    mode = detect_advisor_world_mode(
        "Are there missing worldbuilding gaps or canon contradictions in the magic system?",
        "consistency",
    )

    assert mode == "gap_detection"


def test_detect_advisor_world_mode_ignores_non_lore_questions():
    assert (
        detect_advisor_world_mode("Should my protagonist forgive her brother?", "direction") is None
    )


def test_detect_advisor_world_mode_routes_reaction_questions_to_story_integration():
    mode = detect_advisor_world_mode(
        "How would the river kingdom react if I introduced this trade blockade?",
        "general",
    )

    assert mode == "story_integration"


def test_advisor_retrieval_settings_use_continuity_profile_for_consistency_and_world_mode():
    assert advisor_retrieval_settings("consistency", None) == (12, 0.22)
    assert advisor_retrieval_settings("general", "gap_detection") == (12, 0.22)


def test_advisor_retrieval_settings_use_general_profile_by_default():
    assert advisor_retrieval_settings("general", None) == (8, 0.28)


def test_build_advisor_world_context_compacts_alerts_suggestions_and_citations():
    context = build_advisor_world_context(
        {
            "mode": "gap_detection",
            "answer": "World logic scan found one major canon issue.",
            "logic_alerts": [
                {
                    "title": "Magic rule conflict",
                    "description": "The spell works in chapter 8 but the lore says it requires moonlight.",
                    "suggested_fix": "Add a moonlit source to the scene.",
                }
            ],
            "suggestions": [
                {
                    "element_name": "Moon Gate",
                    "description": "Seed the gate before the battle.",
                }
            ],
            "citations": [
                {
                    "name": "Moon Gate",
                    "element_type": "place",
                    "source_scope": "worldbuilding",
                }
            ],
            "simulation_steps": [
                "Canon focus: Moon Gate behaves as a place with worldbuilding support."
            ],
        }
    )

    assert "WORLD ANALYSIS" in context
    assert "Magic rule conflict" in context
    assert "Moon Gate [place] source=worldbuilding" in context


def test_identify_character_mentions_matches_punctuation_and_possessives():
    matches = identify_character_mentions(
        'Gregor\'s breathing caught. Later, Grete whispered, "Not now."',
        [
            {"name": "Gregor", "aliases": [], "first_chapter": 1},
            {"name": "Grete", "aliases": [], "first_chapter": 1},
            {"name": "Mother", "aliases": [], "first_chapter": 1},
        ],
    )

    assert [item["name"] for item in matches] == ["Gregor", "Grete"]


@pytest.mark.asyncio
async def test_invalidate_advisor_caches_delegates_to_namespace_invalidator(monkeypatch):
    captured = {}

    async def _fake_invalidate(*, book_id=None, series_ids=None):
        captured["book_id"] = book_id
        captured["series_ids"] = series_ids

    monkeypatch.setattr(
        "app.utils.advisor_utils.invalidate_advisor_cache_namespaces",
        _fake_invalidate,
    )

    await invalidate_advisor_caches(book_id="book-key", series_ids=["series-a"])

    assert captured == {"book_id": "book-key", "series_ids": ["series-a"]}


@pytest.mark.asyncio
async def test_invalidate_advisor_caches_for_book_expands_series_scope(monkeypatch):
    captured = {}

    async def _fake_invalidate(*, book_id=None, series_ids=None):
        captured["book_id"] = book_id
        captured["series_ids"] = series_ids

    class _FakeResult:
        def all(self):
            return [
                type("Row", (), {"series_id": "series-a"})(),
                type("Row", (), {"series_id": "series-b"})(),
            ]

    class _FakeDB:
        async def execute(self, *_args, **_kwargs):
            return _FakeResult()

    monkeypatch.setattr(
        "app.utils.advisor_utils.invalidate_advisor_caches",
        _fake_invalidate,
    )

    await invalidate_advisor_caches_for_book(
        _FakeDB(), book_id="12345678-1234-5678-1234-567812345678"
    )

    assert captured == {
        "book_id": "12345678-1234-5678-1234-567812345678",
        "series_ids": ["series-a", "series-b"],
    }


def test_normalize_proactive_scan_result_keeps_valid_findings():
    payload = normalize_proactive_scan_result(
        '{"findings":[{"severity":"warning","type":"event_conflict","title":"Broken alibi","description":"The alibi fails in chapter 9.","chapter_ref":9,"action_label":"Trace the alibi","ask_prompt":"Where does the alibi break?"}],"overall_note":"One continuity risk found."}'
    )

    assert payload["overall_note"] == "One continuity risk found."
    assert payload["findings"][0]["type"] == "event_conflict"
    assert payload["findings"][0]["chapter_ref"] == 9


def test_normalize_proactive_scan_result_falls_back_on_invalid_json():
    payload = normalize_proactive_scan_result("not-json")

    assert payload["findings"] == []
    assert "not-json" in payload["overall_note"]


@pytest.mark.asyncio
async def test_build_story_context_returns_cached_payload(monkeypatch):
    book_id = "12345678-1234-5678-1234-567812345678"

    async def _fake_get_version(_book_id):
        return 0

    async def _fake_get_cache(_book_id, _version, _total_ch):
        return "cached-context"

    async def _fake_set_cache(*_args, **_kwargs):
        raise AssertionError("cache set should not run on cache hit")

    monkeypatch.setattr(
        "app.utils.advisor_story_context_utils.get_book_cache_version", _fake_get_version
    )
    monkeypatch.setattr(
        "app.utils.advisor_story_context_utils.get_story_context_cache", _fake_get_cache
    )
    monkeypatch.setattr(
        "app.utils.advisor_story_context_utils.set_story_context_cache", _fake_set_cache
    )

    class _FailingDB:
        async def execute(self, *_args, **_kwargs):
            raise AssertionError("db should not be queried on cache hit")

    payload = await build_story_context(_FailingDB(), uuid.UUID(book_id), 12)

    assert payload == "cached-context"


@pytest.mark.asyncio
async def test_build_story_context_builds_and_caches_complete_runtime_context(monkeypatch):
    book_id = uuid.uuid4()
    cached_payloads = []

    async def _fake_get_version(_book_id):
        return 4

    async def _fake_get_cache(*_args):
        return None

    async def _fake_set_cache(*args):
        cached_payloads.append(args)

    monkeypatch.setattr(
        "app.utils.advisor_story_context_utils.get_book_cache_version", _fake_get_version
    )
    monkeypatch.setattr(
        "app.utils.advisor_story_context_utils.get_story_context_cache", _fake_get_cache
    )
    monkeypatch.setattr(
        "app.utils.advisor_story_context_utils.set_story_context_cache", _fake_set_cache
    )

    character = SimpleNamespace(
        name="Mara",
        role="mc",
        first_chapter=1,
        arc_summary="Learns to trust the gate council " * 8,
        personality_tags=["guarded", "precise", "loyal", "unused"],
        motivations=["protect the gate", "learn the truth", "unused"],
        growth_events=["invalid", {"event_title": "Hands Joren the key"}],
        trait_state={
            "eyes": {"value": "gray"},
            "hair": "black",
            "build": 42,
            "age_descriptor": {"value": "twenty-nine"},
        },
    )
    book = SimpleNamespace(
        characters=[character],
        plot_threads=[
            SimpleNamespace(
                title="The Brass Key",
                importance=9,
                introduced_at=2,
                status=None,
                description="The key predates the city and may open the ash gate. " * 4,
            )
        ],
        world_elements=[
            SimpleNamespace(
                name="Ash Gate",
                element_type="place",
                usage_count=12,
                description="An ancient silver arch " * 8,
            )
        ],
    )

    class _Result:
        def __init__(self, *, scalar=None, rows=None):
            self.scalar = scalar
            self.rows = rows or []

        def scalars(self):
            return self

        def first(self):
            return self.scalar

        def all(self):
            return list(self.rows)

    class _FakeDB:
        def __init__(self):
            self.results = [
                _Result(scalar=book),
                _Result(rows=[("Gate Codex", "document", "Author supplied canon " * 12, 8)]),
                _Result(
                    rows=[
                        (
                            7,
                            "The Choice",
                            [{"event_title": "Mara opens the gate"}, {"event": " '  "}, "invalid"],
                        ),
                        (6, None, "invalid"),
                    ]
                ),
                _Result(
                    rows=[
                        (
                            7,
                            [
                                {
                                    "theme": "Trust",
                                    "signal": "rising",
                                    "depth": "deep",
                                    "evidence": "Mara shares the key.",
                                },
                                {"theme": ""},
                            ],
                        ),
                        (6, [{"theme": "trust", "evidence": "duplicate"}, "invalid"]),
                    ]
                ),
            ]

        async def execute(self, _statement):
            return self.results.pop(0)

    payload = await build_story_context(_FakeDB(), book_id, 9)

    assert "Total chapters processed: 9" in payload
    assert "CHARACTERS" in payload and "Recent growth beat: Hands Joren the key" in payload
    assert "PLOT THREADS" in payload and "[INTRODUCED] The Brass Key" in payload
    assert "WORLD REFERENCE CORPUS" in payload and "Gate Codex" in payload
    assert "MAJOR EVENTS" in payload and "Mara opens the gate [ch.7 (The Choice)]" in payload
    assert "WORLD ELEMENTS" in payload and "Ash Gate" in payload
    assert payload.count("Trust (chapter") == 1
    assert cached_payloads == [(str(book_id), 4, 9, payload)]


@pytest.mark.asyncio
async def test_classify_response_type_no_llm_warning_marker():
    result = await classify_response_type(None, "⚠️ This contradicts chapter 3")
    assert result == "warning"


@pytest.mark.asyncio
async def test_classify_response_type_no_llm_contradiction_inline():
    result = await classify_response_type(
        None, "Here is an analysis. ⚠️ Contradiction in the timeline"
    )
    assert result == "warning"


@pytest.mark.asyncio
async def test_classify_response_type_no_llm_opportunity_marker():
    result = await classify_response_type(None, "✨ Here is a chance to expand the lore")
    assert result == "opportunity"


@pytest.mark.asyncio
async def test_classify_response_type_no_llm_opportunity_inline():
    result = await classify_response_type(
        None, "Take a look. ✨ Opportunity: unused side character"
    )
    assert result == "opportunity"


@pytest.mark.asyncio
async def test_classify_response_type_no_llm_tradeoff_marker():
    result = await classify_response_type(None, "🔀 Option A: Kill the king. Option B: Spare him.")
    assert result == "tradeoff"


@pytest.mark.asyncio
async def test_classify_response_type_no_llm_fallback_to_standard():
    result = await classify_response_type(
        None, "Here is some general advice about your story pacing."
    )
    assert result == "standard"


@pytest.mark.asyncio
async def test_classify_response_type_no_llm_empty_reply():
    result = await classify_response_type(None, "")
    assert result == "standard"


def test_classify_intent_fast_plothole_exact():
    assert classify_intent_fast("I found a plot hole in chapter 3") == "plothole"


def test_classify_intent_fast_plothole_contradiction():
    assert classify_intent_fast("This contradicts what happened in chapter 1") == "plothole"


def test_classify_intent_fast_plothole_inconsistency():
    assert classify_intent_fast("There is an inconsistency in the timeline") == "plothole"
    assert classify_intent_fast("This doesn't make sense given the lore") == "plothole"


def test_classify_intent_fast_direction_what_should():
    assert classify_intent_fast("What should happen next in the story?") == "direction"


def test_classify_intent_fast_direction_stuck():
    assert (
        classify_intent_fast("I am stuck on this chapter, where do I go from here?") == "direction"
    )


def test_classify_intent_fast_direction_next_step():
    assert classify_intent_fast("What is the next step for my protagonist?") == "direction"


def test_classify_intent_fast_opportunity_potential():
    assert (
        classify_intent_fast("Is there untapped potential in this side character?") == "opportunity"
    )


def test_classify_intent_fast_opportunity_expand():
    assert classify_intent_fast("Could I expand the magic system further?") == "opportunity"


def test_classify_intent_fast_consistency_canon():
    assert (
        classify_intent_fast("Does this new chapter stay consistent with the canon?")
        == "consistency"
    )


def test_classify_intent_fast_consistency_rules():
    assert classify_intent_fast("Are there any worldbuilding rules I'm breaking?") == "consistency"


def test_classify_intent_fast_consistency_timeline():
    assert classify_intent_fast("Check the timeline for continuity errors") == "consistency"


def test_classify_intent_fast_general_unknown():
    assert classify_intent_fast("Hello, how are you doing today?") == "general"


def test_classify_intent_fast_general_empty_string():
    assert classify_intent_fast("") == "general"


def test_classify_intent_fast_general_none():
    assert classify_intent_fast(None) == "general"


def test_classify_intent_fast_mixed_case():
    assert classify_intent_fast("I FOUND A PLOT HOLE in my manuscript") == "plothole"


def test_classify_intent_fast_whitespace_only():
    assert classify_intent_fast("   ") == "general"


def test_classify_intent_fast_direction_should_i():
    assert classify_intent_fast("Should I kill off this character in chapter 5?") == "direction"


@pytest.mark.asyncio
async def test_retrieve_series_continuity_passages_returns_empty_when_pgvector_extension_is_missing():
    class _FakeDB:
        async def execute(self, *_args, **_kwargs):
            raise ProgrammingError(
                "SELECT 1",
                {},
                Exception('type "vector" does not exist'),
            )

    with patch(
        "app.utils.advisor_retrieval_utils.embed_text", AsyncMock(return_value=[0.1] * 1536)
    ):
        payload = await retrieve_series_continuity_passages(
            db=_FakeDB(),
            prior_book_ids=[uuid.uuid4()],
            query="where did this canon start",
            user_id=uuid.uuid4(),
        )

    assert payload == []


# ── language_context_hint ─────────────────────────────────────────────────


def test_language_hint_french():
    hint = language_context_hint("fr")
    assert "French" in hint
    assert "English field names" in hint
    assert "original language" in hint


def test_language_hint_spanish():
    hint = language_context_hint("es")
    assert "Spanish" in hint


def test_language_hint_german():
    hint = language_context_hint("de")
    assert "German" in hint


def test_language_hint_italian():
    hint = language_context_hint("it")
    assert "Italian" in hint


def test_language_hint_portuguese():
    hint = language_context_hint("pt")
    assert "Portuguese" in hint


def test_language_hint_english_returns_empty():
    assert language_context_hint("en") == ""


def test_language_hint_none_returns_empty():
    assert language_context_hint(None) == ""


def test_language_hint_unsupported_returns_empty():
    assert language_context_hint("zh") == ""
    assert language_context_hint("ja") == ""


@pytest.mark.asyncio
async def test_prepare_advisor_reply_context_builds_grounded_messages(monkeypatch):
    closed: list[bool] = []

    class FakeClient:
        async def close(self):
            closed.append(True)

    async def no_cache(*_args, **_kwargs):
        return None

    async def story_context(*_args, **_kwargs):
        return "Mara guards the northern gate."

    async def search(*_args, **_kwargs):
        return [
            {
                "chapter_num": 4,
                "chapter_title": "The Gate",
                "text": "Mara refuses to open the gate.",
                "relevance": 0.88,
            }
        ]

    async def cache_version(*_args, **_kwargs):
        return 0

    monkeypatch.setattr(advisor_chat_utils, "get_openai_client", lambda: FakeClient())
    monkeypatch.setattr(advisor_chat_utils, "get_book_cache_version", cache_version)
    monkeypatch.setattr(advisor_chat_utils, "get_advisor_response_cache", no_cache)
    monkeypatch.setattr(advisor_chat_utils, "build_story_context", story_context)
    monkeypatch.setattr(advisor_chat_utils, "semantic_search", search)
    monkeypatch.setattr(advisor_chat_utils, "classify_intent_fast", lambda _text: "consistency")

    book = SimpleNamespace(id=uuid.uuid4(), title="Gate Book", total_chapters=6)
    prepared = await advisor_chat_utils.prepare_advisor_reply_context(
        db=SimpleNamespace(),
        book=book,
        user_id=uuid.uuid4(),
        messages=[
            {"role": "assistant", "content": "What should I inspect?"},
            {"role": "user", "content": "Does Mara contradict the gate rule?"},
        ],
        total_chapters=6,
    )

    assert prepared["cached"] is None
    assert prepared["intent"] == "consistency"
    assert prepared["hits"][0]["chapter_num"] == 4
    assert "Retrieved passages" in prepared["llm_messages"][-1]["content"]
    assert "Chapter 4" in prepared["llm_messages"][-1]["content"]
    assert closed == []

    async def cached(*_args, **_kwargs):
        return {"reply": "Cached answer"}

    monkeypatch.setattr(advisor_chat_utils, "get_advisor_response_cache", cached)
    cached_payload = await advisor_chat_utils.prepare_advisor_reply_context(
        db=SimpleNamespace(),
        book=book,
        user_id=uuid.uuid4(),
        messages=[{"role": "user", "content": "Same question"}],
        total_chapters=6,
    )
    assert cached_payload == {"cached": {"reply": "Cached answer", "cached": True}}


@pytest.mark.asyncio
async def test_build_series_story_context_labels_books_characters_and_threads(db, monkeypatch):
    user = User(
        email=f"series-context-{uuid.uuid4().hex[:8]}@lorevia.app",
        username=f"seriescontext{uuid.uuid4().hex[:8]}",
        password_hash="hash",
    )
    db.add(user)
    await db.flush()
    series = Series(user_id=user.id, name="Winter Cycle")
    db.add(series)
    await db.flush()
    books = [
        Book(
            user_id=user.id, title="Ice Gate", format="txt", s3_key="series/ice.txt", status="ready"
        ),
        Book(
            user_id=user.id,
            title="Ash Crown",
            format="txt",
            s3_key="series/ash.txt",
            status="ready",
        ),
    ]
    db.add_all(books)
    await db.flush()
    db.add_all(
        [
            SeriesBook(series_id=series.id, book_id=books[0].id, position=1),
            SeriesBook(series_id=series.id, book_id=books[1].id, position=2),
            Character(
                book_id=books[0].id,
                name="Mara",
                normalized_name="mara",
                role="protagonist",
                first_chapter=1,
                arc_summary="Learns why the gate was sealed.",
                personality_tags=["resolute"],
                motivations=["protect the city"],
            ),
            PlotThread(
                book_id=books[0].id,
                title="The sealed gate",
                description="The old gate cannot be opened safely.",
                status="developing",
                introduced_at=2,
                importance=8,
            ),
        ]
    )
    await db.commit()

    async def version(*_args, **_kwargs):
        return 2

    async def no_cache(*_args, **_kwargs):
        return None

    stored: dict[str, object] = {}

    async def set_cache(key, version_value, payload):
        stored.update(key=key, version=version_value, payload=payload)

    monkeypatch.setattr("app.utils.advisor_story_context_utils.get_book_cache_version", version)
    monkeypatch.setattr("app.utils.advisor_story_context_utils.get_series_cache_version", version)
    monkeypatch.setattr(
        "app.utils.advisor_story_context_utils.get_series_story_context_cache", no_cache
    )
    monkeypatch.setattr(
        "app.utils.advisor_story_context_utils.set_series_story_context_cache", set_cache
    )

    payload = await build_series_story_context(
        db,
        [book.id for book in books],
        {book.id: book.title for book in books},
    )

    assert "Book: Ice Gate" in payload
    assert "Book: Ash Crown" in payload
    assert "Mara" in payload
    assert "The sealed gate" in payload
    assert stored["payload"] == payload


@pytest.mark.asyncio
async def test_stream_advisor_payload_records_usage_and_finalizes(monkeypatch):
    closed: list[bool] = []

    async def chunks():
        yield SimpleNamespace(
            usage=SimpleNamespace(prompt_tokens=10, completion_tokens=4, total_tokens=14),
            choices=[SimpleNamespace(delta=SimpleNamespace(content="First "))],
        )
        yield SimpleNamespace(
            usage=None, choices=[SimpleNamespace(delta=SimpleNamespace(content="answer"))]
        )

    class Completions:
        async def create(self, **_kwargs):
            return chunks()

    class Client:
        chat = SimpleNamespace(completions=Completions())

        async def close(self):
            closed.append(True)

    async def prepare(**_kwargs):
        return {
            "cached": None,
            "client": Client(),
            "cache_key": "cache-key",
            "cache_version": 0,
            "intent": "direction",
            "hits": [],
            "world_analysis": None,
            "llm_messages": [{"role": "user", "content": "Question"}],
        }

    usage: list[dict] = []

    async def capacity(*_args, **_kwargs):
        return None

    async def reserve(**kwargs):
        return SimpleNamespace(
            id="advisor-reservation", operation="chat", user_id=kwargs["user_id"]
        )

    async def finish(_reservation, **kwargs):
        usage.append(kwargs)

    async def finalize(**kwargs):
        return {"reply": kwargs["reply"], "cached": False}

    monkeypatch.setattr(advisor_chat_utils, "prepare_advisor_reply_context", prepare)
    monkeypatch.setattr(advisor_chat_utils, "reserve_llm_call", reserve)
    monkeypatch.setattr(advisor_chat_utils, "finish_llm_reservation_counts", finish)
    monkeypatch.setattr(advisor_chat_utils, "finalize_advisor_reply_payload", finalize)

    events = [
        event
        async for event in advisor_chat_utils.stream_advisor_reply_payload(
            db=SimpleNamespace(),
            book=SimpleNamespace(id=uuid.uuid4()),
            user_id=uuid.uuid4(),
            messages=[{"role": "user", "content": "Question"}],
            total_chapters=3,
        )
    ]
    assert [event["event"] for event in events] == ["delta", "delta", "done"]
    assert events[-1]["data"]["reply"] == "First answer"
    assert usage[0]["total_tokens"] == 14
    assert closed == []


@pytest.mark.asyncio
async def test_stream_advisor_payload_settles_success_when_usage_trailer_is_missing(monkeypatch):
    async def chunks():
        yield SimpleNamespace(
            usage=None,
            choices=[SimpleNamespace(delta=SimpleNamespace(content="Answer"))],
        )

    class Completions:
        async def create(self, **_kwargs):
            return chunks()

    class Client:
        chat = SimpleNamespace(completions=Completions())

        async def close(self):
            return None

    async def prepare(**_kwargs):
        return {
            "cached": None,
            "client": Client(),
            "cache_key": "cache-key",
            "cache_version": 0,
            "intent": "direction",
            "hits": [],
            "world_analysis": None,
            "llm_messages": [{"role": "user", "content": "Question"}],
        }

    reservation = SimpleNamespace(id="advisor-reservation", operation="chat", user_id=uuid.uuid4())
    settled: list[object] = []

    async def reserve(**_kwargs):
        return reservation

    async def finish(completed_reservation, response):
        assert response is None
        settled.append(completed_reservation)

    async def fail(*_args, **_kwargs):
        raise AssertionError("a completed provider stream must not be settled as failed")

    async def finalize(**kwargs):
        return {"reply": kwargs["reply"]}

    monkeypatch.setattr(advisor_chat_utils, "prepare_advisor_reply_context", prepare)
    monkeypatch.setattr(advisor_chat_utils, "reserve_llm_call", reserve)
    monkeypatch.setattr(advisor_chat_utils, "finish_llm_reservation", finish)
    monkeypatch.setattr(advisor_chat_utils, "fail_llm_reservation", fail)
    monkeypatch.setattr(advisor_chat_utils, "finalize_advisor_reply_payload", finalize)

    events = [
        event
        async for event in advisor_chat_utils.stream_advisor_reply_payload(
            db=SimpleNamespace(),
            book=SimpleNamespace(id=uuid.uuid4()),
            user_id=uuid.uuid4(),
            messages=[{"role": "user", "content": "Question"}],
            total_chapters=3,
        )
    ]

    assert [event["event"] for event in events] == ["delta", "done"]
    assert settled == [reservation]


@pytest.mark.asyncio
async def test_stream_series_advisor_payload_records_usage_and_finalizes(monkeypatch):
    closed: list[bool] = []

    async def chunks():
        yield SimpleNamespace(
            usage=SimpleNamespace(prompt_tokens=12, completion_tokens=3, total_tokens=15),
            choices=[SimpleNamespace(delta=SimpleNamespace(content="Series answer"))],
        )

    class Completions:
        async def create(self, **_kwargs):
            return chunks()

    class Client:
        chat = SimpleNamespace(completions=Completions())

        async def close(self):
            closed.append(True)

    async def prepare(**_kwargs):
        return {
            "cached": None,
            "client": Client(),
            "cache_key": "series-cache",
            "cache_version": 0,
            "intent": "consistency",
            "book_count": 2,
            "llm_messages": [{"role": "user", "content": "Compare volumes"}],
        }

    usage: list[dict] = []

    async def capacity(*_args, **_kwargs):
        return None

    async def reserve(**kwargs):
        return SimpleNamespace(id="series-reservation", operation="chat", user_id=kwargs["user_id"])

    async def finish(_reservation, **kwargs):
        usage.append(kwargs)

    async def finalize(**kwargs):
        return {"reply": kwargs["reply"], "book_count": kwargs["book_count"]}

    monkeypatch.setattr(advisor_chat_utils, "prepare_series_advisor_reply_context", prepare)
    monkeypatch.setattr(advisor_chat_utils, "reserve_llm_call", reserve)
    monkeypatch.setattr(advisor_chat_utils, "finish_llm_reservation_counts", finish)
    monkeypatch.setattr(advisor_chat_utils, "finalize_series_advisor_reply_payload", finalize)

    series = SimpleNamespace(id=uuid.uuid4())
    events = [
        event
        async for event in advisor_chat_utils.stream_series_advisor_reply_payload(
            db=SimpleNamespace(),
            series=series,
            user_id=uuid.uuid4(),
            messages=[{"role": "user", "content": "Compare volumes"}],
        )
    ]
    assert [event["event"] for event in events] == ["delta", "done"]
    assert events[-1]["data"] == {"reply": "Series answer", "book_count": 2}
    assert usage[0]["total_tokens"] == 15
    assert closed == []


@pytest.mark.asyncio
async def test_prepare_series_advisor_context_builds_history_and_handles_empty_series(monkeypatch):
    series_id = uuid.uuid4()
    book_id = uuid.uuid4()

    class Result:
        def __init__(self, rows):
            self.rows = rows

        def all(self):
            return list(self.rows)

    class Db:
        def __init__(self, results):
            self.results = list(results)

        async def execute(self, _statement):
            return Result(self.results.pop(0))

    async def no_cache(*_args, **_kwargs):
        return None

    async def context(*_args, **_kwargs):
        return "Earlier volume context"

    async def cache_version(*_args, **_kwargs):
        return 0

    class Client:
        async def close(self):
            return None

    monkeypatch.setattr(advisor_chat_utils, "get_series_advisor_response_cache", no_cache)
    monkeypatch.setattr(advisor_chat_utils, "get_series_cache_version", cache_version)
    monkeypatch.setattr(advisor_chat_utils, "build_series_story_context", context)
    monkeypatch.setattr(advisor_chat_utils, "get_openai_client", lambda: Client())
    monkeypatch.setattr(advisor_chat_utils, "classify_intent_fast", lambda _text: "opportunity")

    prepared = await advisor_chat_utils.prepare_series_advisor_reply_context(
        db=Db(
            [
                [SimpleNamespace(book_id=book_id, position=1)],
                [SimpleNamespace(id=book_id, title="Volume One")],
            ]
        ),
        series=SimpleNamespace(id=series_id, name="Cycle"),
        user_id=uuid.uuid4(),
        messages=[
            {"role": "assistant", "content": "What should we compare?"},
            {"role": "user", "content": "Where can volume two echo volume one?"},
        ],
    )
    assert prepared["book_count"] == 1
    assert prepared["intent"] == "opportunity"
    assert "Earlier volume context" in prepared["llm_messages"][0]["content"]
    assert prepared["llm_messages"][-1]["content"].startswith("Where can")

    with pytest.raises(ValueError, match="no_books_found_in_series"):
        await advisor_chat_utils.prepare_series_advisor_reply_context(
            db=Db([[]]),
            series=SimpleNamespace(id=series_id, name="Empty Cycle"),
            user_id=uuid.uuid4(),
            messages=[{"role": "user", "content": "Compare the books"}],
        )
