from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1.routes import advisor
from app.schemas.advisor import (
    AdvisorMessage,
    AdvisorRequest,
    EditorialReviewRequest,
    InlineContinuityRequest,
    ProseTightenRequest,
    VoiceConsistencyRequest,
)


class _ScalarList:
    def __init__(self, items):
        self._items = items

    def all(self):
        return list(self._items)


class _MappingList:
    def __init__(self, items):
        self._items = items

    def all(self):
        return list(self._items)


class _Result:
    def __init__(
        self,
        *,
        scalar=None,
        scalar_one=None,
        all_rows=None,
        scalars=None,
        mappings=None,
        fetchall_rows=None,
    ):
        self._scalar = scalar
        self._scalar_one = scalar if scalar_one is None else scalar_one
        self._all_rows = [] if all_rows is None else all_rows
        self._scalars = [] if scalars is None else scalars
        self._mappings = [] if mappings is None else mappings
        self._fetchall_rows = self._all_rows if fetchall_rows is None else fetchall_rows

    def scalar(self):
        return self._scalar

    def scalar_one(self):
        return self._scalar_one

    def all(self):
        return list(self._all_rows)

    def scalars(self):
        return _ScalarList(self._scalars)

    def mappings(self):
        return _MappingList(self._mappings)

    def fetchall(self):
        return list(self._fetchall_rows)


class _FakeDB:
    def __init__(self, *, get_values=None, execute_values=None):
        self._get_values = list(get_values or [])
        self._execute_values = list(execute_values or [])

    async def get(self, *_args, **_kwargs):
        return self._get_values.pop(0)

    async def execute(self, *_args, **_kwargs):
        return self._execute_values.pop(0)


class _FakeClient:
    def __init__(self, *contents: str):
        self._contents = list(contents)
        self.closed = False
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, **kwargs):
        self.calls.append(kwargs)
        content = self._contents.pop(0) if self._contents else "{}"
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )

    async def close(self):
        self.closed = True


class _Cache:
    def __init__(self, data=None):
        self.data = dict(data or {})
        self.set_calls = []

    def get(self, key):
        return self.data.get(key)

    def set(self, key, value):
        self.data[key] = value
        self.set_calls.append((key, value))


def _message_body(*messages: tuple[str, str], total_chapters: int = 12) -> AdvisorRequest:
    return AdvisorRequest(
        messages=[AdvisorMessage(role=role, content=content) for role, content in messages],
        total_chapters=total_chapters,
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Name {test}", "Name {{test}}"),
        ("Already } odd {", "Already }} odd {{"),
        (None, ""),
    ],
)
def test_safe_prompt_str_escapes_braces(value, expected):
    assert advisor._safe_prompt_str(value) == expected


def test_best_issue_snippet_prefers_matching_sentence_and_falls_back():
    text = "A quiet setup. The silver key disappears during the storm. Another ending sentence."
    description = "Missing silver key contradiction"
    assert advisor._best_issue_snippet(text, description) == "The silver key disappears during the storm."
    assert advisor._best_issue_snippet("No punctuation here", "missing") == "No punctuation here"


@pytest.mark.asyncio
async def test_advisor_message_validates_book_and_messages():
    db = _FakeDB(get_values=[None])
    body = _message_body(("user", "Help"))
    with pytest.raises(HTTPException) as exc:
        await advisor.advisor_message(
            uuid.uuid4(),
            body=body,
            db=db,
            current_user=SimpleNamespace(id=uuid.uuid4()),
            _=None,
        )
    assert exc.value.status_code == 404

    user_id = uuid.uuid4()
    book = SimpleNamespace(id=uuid.uuid4(), user_id=user_id, title="Atlas", total_chapters=8)
    db = _FakeDB(get_values=[book])
    with pytest.raises(HTTPException) as exc:
        await advisor.advisor_message(
            book.id,
            body=AdvisorRequest(messages=[]),
            db=db,
            current_user=SimpleNamespace(id=user_id),
            _=None,
        )
    assert exc.value.detail == "messages list is empty"

    db = _FakeDB(get_values=[book])
    with pytest.raises(HTTPException) as exc:
        await advisor.advisor_message(
            book.id,
            body=_message_body(("assistant", "Only assistant")),
            db=db,
            current_user=SimpleNamespace(id=user_id),
            _=None,
        )
    assert exc.value.detail == "no user message found"


@pytest.mark.asyncio
async def test_advisor_message_returns_cached_payload(monkeypatch):
    book_id = uuid.uuid4()
    user_id = uuid.uuid4()
    book = SimpleNamespace(id=book_id, user_id=user_id, title="Atlas", total_chapters=8)
    cache = _Cache({"cached-key": {"reply": "Cached", "intent": "direction"}})
    monkeypatch.setattr(advisor, "make_advisor_cache_key", lambda *_args: "cached-key")
    monkeypatch.setattr(advisor, "advisor_response_cache", cache)
    db = _FakeDB(get_values=[book])

    payload = await advisor.advisor_message(
        book_id,
        body=_message_body(("user", "What next?")),
        db=db,
        current_user=SimpleNamespace(id=user_id),
        _=None,
    )

    assert payload["reply"] == "Cached"
    assert payload["cached"] is True


@pytest.mark.asyncio
async def test_advisor_message_builds_response_and_caches(monkeypatch):
    book_id = uuid.uuid4()
    user_id = uuid.uuid4()
    book = SimpleNamespace(id=book_id, user_id=user_id, title="Atlas {Saga}", total_chapters=12)
    hits = [
        SimpleNamespace(text="Storm clues matter here.", chapter_num=3, chapter_title="Storm", relevance=0.91),
        SimpleNamespace(text="World lore excerpt.", chapter_num=4, chapter_title=None, relevance=0.73),
    ]
    db = _FakeDB(get_values=[book], execute_values=[_Result(fetchall_rows=hits)])
    cache = _Cache()
    client = _FakeClient("Advisor reply")

    async def _fake_classify_intent(_client, _message):
        return "consistency"

    async def _fake_build_story_context(*_args, **_kwargs):
        return "Story context"

    async def _fake_build_world_analysis(*_args, **_kwargs):
        return {"mode": "gap_detection", "summary": "World gaps"}

    async def _fake_embed_text(_text):
        return [0.1, 0.2]

    async def _fake_classify_response_type(_client, _reply):
        return "analysis"

    monkeypatch.setattr(advisor, "make_advisor_cache_key", lambda *_args: "advisor-key")
    monkeypatch.setattr(advisor, "advisor_response_cache", cache)
    monkeypatch.setattr(advisor, "AsyncOpenAI", lambda api_key: client)
    monkeypatch.setattr(advisor, "classify_intent", _fake_classify_intent)
    monkeypatch.setattr(advisor, "build_story_context", _fake_build_story_context)
    monkeypatch.setattr(advisor, "detect_advisor_world_mode", lambda *_args: "gap_detection")
    monkeypatch.setattr(advisor, "build_advisor_world_analysis", _fake_build_world_analysis)
    monkeypatch.setattr(advisor, "build_advisor_world_context", lambda world: f"WORLD: {world['summary']}")
    monkeypatch.setattr(advisor, "embed_text", _fake_embed_text)
    monkeypatch.setattr(advisor, "classify_response_type", _fake_classify_response_type)

    payload = await advisor.advisor_message(
        book_id,
        body=_message_body(("assistant", "Context"), ("user", "Check the storm lore"), total_chapters=8),
        db=db,
        current_user=SimpleNamespace(id=user_id),
        _=None,
    )

    assert payload["reply"] == "Advisor reply"
    assert payload["intent"] == "consistency"
    assert payload["world_analysis"]["summary"] == "World gaps"
    assert payload["retrieved_passages"][0]["chapter_num"] == 3
    assert cache.set_calls
    assert client.closed is True
    sent_messages = client.calls[0]["messages"]
    assert "Atlas {{Saga}}" in sent_messages[0]["content"]
    assert "WORLD: World gaps" in sent_messages[-1]["content"]


@pytest.mark.asyncio
async def test_advisor_greeting_counts_entities():
    book_id = uuid.uuid4()
    user_id = uuid.uuid4()
    book = SimpleNamespace(id=book_id, user_id=user_id, title="Atlas", total_chapters=11)
    db = _FakeDB(
        get_values=[book],
        execute_values=[_Result(scalar_one=4), _Result(scalar_one=9)],
    )

    payload = await advisor.advisor_greeting(book_id, db=db, current_user=SimpleNamespace(id=user_id))

    assert payload["book_title"] == "Atlas"
    assert payload["stats"] == {"characters": 9, "plot_threads": 4, "total_chapters": 11}


@pytest.mark.asyncio
async def test_advisor_suggestions_collects_sorted_categories():
    book_id = uuid.uuid4()
    user_id = uuid.uuid4()
    char_id = uuid.uuid4()
    thread_id = uuid.uuid4()
    book = SimpleNamespace(id=book_id, user_id=user_id, title="Atlas", total_chapters=40)
    states = [
        SimpleNamespace(
            character_id=char_id,
            at_chapter=2,
            trait_snapshot={"eyes": {"value": "blue"}},
            name="Iris",
        ),
        SimpleNamespace(
            character_id=char_id,
            at_chapter=9,
            trait_snapshot={"eyes": {"value": "green"}},
            name="Iris",
        ),
    ]
    dropped = SimpleNamespace(
        id=thread_id,
        title="Locked Door",
        status="ongoing",
        introduced_at=2,
        description="Door mystery",
        importance=8,
    )
    absent = SimpleNamespace(
        id=uuid.uuid4(),
        name="Milo",
        mention_count=10,
        last_seen_chapter=5,
        role="ally",
        arc_summary="Waiting off page",
    )
    underused = SimpleNamespace(
        id=uuid.uuid4(),
        name="Nia",
        mention_count=9,
        first_chapter=3,
    )
    recent_summaries = [
        (["Rust key"], 4, "Vault"),
        ({"one": "Hidden map"}, 5, "Tunnel"),
    ]
    db = _FakeDB(
        get_values=[book],
        execute_values=[
            _Result(all_rows=states),
            _Result(scalars=[dropped]),
            _Result(scalars=[absent]),
            _Result(scalars=[dropped]),
            _Result(scalars=[dropped]),
            _Result(scalars=[underused]),
            _Result(all_rows=recent_summaries),
        ],
    )

    payload = await advisor.advisor_suggestions(book_id, db=db, current_user=SimpleNamespace(id=user_id))

    assert payload["total"] >= 6
    types = [item["type"] for item in payload["suggestions"]]
    assert "trait_contradiction" in types
    assert "dropped_thread" in types
    assert "character_absent" in types
    assert "arc_opportunity" in types
    assert "foreshadowing_opportunity" in types
    assert "unresolved_clue" in types
    severities = [item["severity"] for item in payload["suggestions"]]
    assert severities == sorted(severities, key=lambda item: {"warning": 0, "direction": 1, "opportunity": 2, "info": 3}.get(item, 4))


@pytest.mark.asyncio
async def test_editorial_review_validates_cache_and_happy_path(monkeypatch):
    book_id = uuid.uuid4()
    user_id = uuid.uuid4()
    book = SimpleNamespace(id=book_id, user_id=user_id, title="Atlas", total_chapters=9)

    db = _FakeDB(get_values=[book])
    with pytest.raises(HTTPException) as exc:
        await advisor.editorial_review(
            book_id,
            body=EditorialReviewRequest(text="   ", chapter_num=2),
            db=db,
            current_user=SimpleNamespace(id=user_id),
            _=None,
        )
    assert exc.value.detail == "Passage text is required."

    cache = _Cache({"editorial-key": {"review": {"overall_verdict": "Cached"}, "retrieved_passages": []}})
    monkeypatch.setattr(advisor, "make_editorial_cache_key", lambda *_args: "editorial-key")
    monkeypatch.setattr(advisor, "advisor_response_cache", cache)
    db = _FakeDB(get_values=[book])
    cached_payload = await advisor.editorial_review(
        book_id,
        body=EditorialReviewRequest(text="Scene", chapter_num=2),
        db=db,
        current_user=SimpleNamespace(id=user_id),
        _=None,
    )
    assert cached_payload["cached"] is True

    cache = _Cache()
    client = _FakeClient('{"overall_verdict":"Needs polish"}')

    async def _fake_semantic_search(*_args, **_kwargs):
        return [{"chapter_num": 2, "chapter_title": "Storm", "chunk_index": 7, "text": "Passage", "score": 0.81}]

    async def _fake_story_context(*_args, **_kwargs):
        return "Story context"

    monkeypatch.setattr(advisor, "advisor_response_cache", cache)
    monkeypatch.setattr(advisor, "make_editorial_cache_key", lambda *_args: "editorial-build")
    monkeypatch.setattr(advisor, "semantic_search", _fake_semantic_search)
    monkeypatch.setattr(advisor, "build_story_context", _fake_story_context)
    monkeypatch.setattr(advisor, "normalize_editorial_review_result", lambda raw: {"overall_verdict": raw})
    monkeypatch.setattr(advisor, "AsyncOpenAI", lambda api_key: client)
    db = _FakeDB(get_values=[book])

    payload = await advisor.editorial_review(
        book_id,
        body=EditorialReviewRequest(text="Scene", chapter_num=2),
        db=db,
        current_user=SimpleNamespace(id=user_id),
        _=None,
    )

    assert payload["review"]["overall_verdict"] == '{"overall_verdict":"Needs polish"}'
    assert payload["retrieved_passages"][0]["chunk_index"] == 7
    assert cache.set_calls
    assert client.closed is True


@pytest.mark.asyncio
async def test_prose_tighten_requires_text_and_normalizes(monkeypatch):
    book_id = uuid.uuid4()
    user_id = uuid.uuid4()
    book = SimpleNamespace(id=book_id, user_id=user_id, title="Atlas")
    db = _FakeDB(get_values=[book])

    with pytest.raises(HTTPException):
        await advisor.prose_tighten(
            book_id,
            body=ProseTightenRequest(text=" "),
            db=db,
            current_user=SimpleNamespace(id=user_id),
            _=None,
        )

    client = _FakeClient('{"tightened_text":"Trimmed","changed":true,"rationale":["Sharper"]}')
    monkeypatch.setattr(advisor, "AsyncOpenAI", lambda api_key: client)
    monkeypatch.setattr(
        advisor,
        "normalize_prose_tighten_result",
        lambda raw, _text: {"tightened_text": "Trimmed", "changed": True, "rationale": [raw]},
    )
    db = _FakeDB(get_values=[book])

    payload = await advisor.prose_tighten(
        book_id,
        body=ProseTightenRequest(text="Long text", chapter_num=4),
        db=db,
        current_user=SimpleNamespace(id=user_id),
        _=None,
    )

    assert payload.tightened_text == "Trimmed"
    assert payload.rationale[0].startswith("{")
    assert client.closed is True


@pytest.mark.asyncio
async def test_inline_continuity_check_uses_editorial_review_and_flags(monkeypatch):
    book_id = uuid.uuid4()
    user_id = uuid.uuid4()
    book = SimpleNamespace(id=book_id, user_id=user_id, title="Atlas")
    db = _FakeDB(get_values=[book])

    async def _fake_editorial_review(**_kwargs):
        return {
            "review": {
                "continuity_issues": [
                    {
                        "severity": "high",
                        "title": "Mismatch",
                        "description": "The silver key changed hands unexpectedly.",
                        "suggestion": "Track the handoff.",
                    }
                ],
                "overall_verdict": "Needs work",
            },
            "retrieved_passages": [{"chapter_num": 2, "excerpt": "Key transfer"}],
        }

    async def _fake_detect_flags(*_args, **_kwargs):
        return ["Memory says the key stayed with Iris."]

    monkeypatch.setattr(advisor, "editorial_review", _fake_editorial_review)
    monkeypatch.setattr(advisor, "detect_chapter_continuity_flags", _fake_detect_flags)

    payload = await advisor.inline_continuity_check(
        book_id,
        body=InlineContinuityRequest(text="Iris drops the key.", chapter_num=3),
        db=db,
        current_user=SimpleNamespace(id=user_id),
        _=None,
    )

    assert payload.overall_verdict == "Needs work"
    assert len(payload.issues) == 2
    assert payload.memory_bank == ["Chapter 2: Key transfer"]


@pytest.mark.asyncio
async def test_manuscript_synopsis_requires_chapters_and_returns_coverage(monkeypatch):
    book_id = uuid.uuid4()
    user_id = uuid.uuid4()
    book = SimpleNamespace(id=book_id, user_id=user_id, title="Atlas", total_chapters=6)
    db = _FakeDB(get_values=[book], execute_values=[_Result(all_rows=[])])

    with pytest.raises(HTTPException) as exc:
        await advisor.manuscript_synopsis(book_id, db=db, current_user=SimpleNamespace(id=user_id))
    assert exc.value.detail == "No chapters available for synopsis generation."

    db = _FakeDB(
        get_values=[book],
        execute_values=[_Result(all_rows=[(1, "Start", "s3://one"), (2, None, None)])],
    )
    client = _FakeClient('{"synopsis":"Short"}')
    monkeypatch.setattr(advisor, "download_book", lambda _key: b"Chapter text")
    async def _fake_story_context(*_args, **_kwargs):
        return "Story context"

    monkeypatch.setattr(advisor, "build_story_context", _fake_story_context)
    monkeypatch.setattr(advisor, "AsyncOpenAI", lambda api_key: client)
    monkeypatch.setattr(advisor, "normalize_synopsis_result", lambda raw, _spoiler: {"synopsis": raw})

    payload = await advisor.manuscript_synopsis(book_id, db=db, current_user=SimpleNamespace(id=user_id))

    assert payload["synopsis"].startswith("{")
    assert payload["coverage_chapters"] == [1, 2]
    assert client.closed is True


@pytest.mark.asyncio
async def test_voice_consistency_review_builds_character_matches(monkeypatch):
    book_id = uuid.uuid4()
    user_id = uuid.uuid4()
    char_id = uuid.uuid4()
    other_id = uuid.uuid4()
    book = SimpleNamespace(id=book_id, user_id=user_id, title="Atlas", total_chapters=9)
    profile = SimpleNamespace(
        character_id=char_id,
        sample_dialogue_count=2,
        sample_word_count=50,
        avg_sentence_length=8,
        avg_word_length_x100=420,
        contraction_rate_x1000=10,
        question_rate_x1000=20,
        exclamation_rate_x1000=5,
        ellipsis_rate_x1000=0,
        dash_rate_x1000=1,
        uppercase_rate_x1000=0,
        formality_score_x1000=500,
        lexical_complexity_x1000=550,
        emotional_intensity_x1000=600,
    )
    other_profile = SimpleNamespace(
        character_id=other_id,
        sample_dialogue_count=3,
        sample_word_count=60,
        avg_sentence_length=9,
        avg_word_length_x100=430,
        contraction_rate_x1000=11,
        question_rate_x1000=18,
        exclamation_rate_x1000=4,
        ellipsis_rate_x1000=0,
        dash_rate_x1000=1,
        uppercase_rate_x1000=0,
        formality_score_x1000=490,
        lexical_complexity_x1000=540,
        emotional_intensity_x1000=590,
    )
    db = _FakeDB(
        get_values=[book],
        execute_values=[
            _Result(mappings=[{"id": char_id, "name": "Iris"}, {"id": other_id, "name": "Milo"}]),
            _Result(scalars=[profile, other_profile]),
        ],
    )
    client = _FakeClient('{"overall":"steady"}')

    async def _fake_semantic_search(*_args, **_kwargs):
        return [{"chapter_num": 2, "chapter_title": "Storm", "chunk_index": 5, "text": "Excerpt", "score": 0.88}]

    async def _fake_story_context(*_args, **_kwargs):
        return "Story context"

    monkeypatch.setattr(advisor, "semantic_search", _fake_semantic_search)
    monkeypatch.setattr(advisor, "build_story_context", _fake_story_context)
    monkeypatch.setattr(advisor, "identify_character_mentions", lambda _text, rows: [rows[0]])
    monkeypatch.setattr(advisor, "extract_dialogue_samples_by_character", lambda *_args: {})
    monkeypatch.setattr(advisor, "build_character_voice_context", lambda chars: f"chars:{len(chars)}")
    monkeypatch.setattr(advisor, "normalize_voice_consistency_result", lambda raw: {"review": raw})
    monkeypatch.setattr(advisor, "compute_voice_metrics", lambda samples: {"sample_dialogue_count": len(samples)})
    monkeypatch.setattr(advisor, "score_voice_match", lambda _profile, metrics: (0.87 if metrics["sample_dialogue_count"] else 0.52, ["cadence"]))
    monkeypatch.setattr(advisor, "AsyncOpenAI", lambda api_key: client)

    payload = await advisor.voice_consistency_review(
        book_id,
        body=VoiceConsistencyRequest(text="Iris says hello.", chapter_num=3),
        db=db,
        current_user=SimpleNamespace(id=user_id),
        _=None,
    )

    assert payload["characters_reviewed"] == ["Iris"]
    assert payload["character_matches"][0]["character_name"] == "Iris"
    assert payload["character_matches"][0]["closest_other_character"] == "Milo"
    assert client.closed is True


@pytest.mark.asyncio
async def test_continuity_report_supports_markdown_and_pdf(monkeypatch):
    book_id = uuid.uuid4()
    user_id = uuid.uuid4()
    book = SimpleNamespace(id=book_id, user_id=user_id, title="Atlas Draft")
    db = _FakeDB(get_values=[book, book])

    async def _fake_editorial_review(**_kwargs):
        return {"review": {"overall_verdict": "ok"}, "retrieved_passages": [{"excerpt": "A"}]}

    async def _fake_suggestions(**_kwargs):
        return {"suggestions": [{"type": "dropped_thread", "title": "Door"}]}

    monkeypatch.setattr(advisor, "editorial_review", _fake_editorial_review)
    monkeypatch.setattr(advisor, "advisor_suggestions", _fake_suggestions)
    monkeypatch.setattr(advisor, "build_continuity_report_markdown", lambda **_kwargs: "# Report")
    monkeypatch.setattr(advisor, "build_continuity_report_pdf", lambda markdown, **_kwargs: markdown.encode("utf-8"))

    md_response = await advisor.continuity_report(
        book_id,
        text="Scene",
        chapter_num=2,
        format="md",
        db=db,
        current_user=SimpleNamespace(id=user_id),
        _=None,
    )
    pdf_response = await advisor.continuity_report(
        book_id,
        text="Scene",
        chapter_num=2,
        format="pdf",
        db=db,
        current_user=SimpleNamespace(id=user_id),
        _=None,
    )

    assert md_response.media_type == "text/markdown; charset=utf-8"
    assert pdf_response.media_type == "application/pdf"


@pytest.mark.asyncio
async def test_series_advisor_message_handles_cache_empty_and_success(monkeypatch):
    series_id = uuid.uuid4()
    user_id = uuid.uuid4()
    book_id = uuid.uuid4()
    series = SimpleNamespace(id=series_id, user_id=user_id, name="Atlas Saga")
    cache = _Cache()
    client = _FakeClient("Series reply")

    monkeypatch.setattr(advisor, "advisor_response_cache", cache)
    monkeypatch.setattr(advisor, "make_advisor_cache_key", lambda *_args: "series-key")
    monkeypatch.setattr(advisor, "AsyncOpenAI", lambda api_key: client)
    async def _fake_series_story_context(*_args, **_kwargs):
        return "Series context"

    monkeypatch.setattr(advisor, "build_series_story_context", _fake_series_story_context)
    async def _fake_classify_response_type(_client, _reply):
        return "analysis"

    async def _fake_classify_intent(_client, _message):
        return "direction"

    monkeypatch.setattr(advisor, "classify_response_type", _fake_classify_response_type)
    monkeypatch.setattr(advisor, "classify_intent", _fake_classify_intent)

    db = _FakeDB(get_values=[series], execute_values=[_Result(all_rows=[])])
    with pytest.raises(HTTPException) as exc:
        await advisor.series_advisor_message(
            series_id,
            body=_message_body(("user", "Anything?")),
            db=db,
            current_user=SimpleNamespace(id=user_id),
            _=None,
        )
    assert exc.value.detail == "No books found in this series."

    db = _FakeDB(
        get_values=[series],
        execute_values=[
            _Result(all_rows=[SimpleNamespace(book_id=book_id, position=1)]),
            _Result(all_rows=[SimpleNamespace(id=book_id, title="Book One")]),
        ],
    )
    payload = await advisor.series_advisor_message(
        series_id,
        body=_message_body(("assistant", "ctx"), ("user", "Anything?")),
        db=db,
        current_user=SimpleNamespace(id=user_id),
        _=None,
    )

    assert payload["reply"] == "Series reply"
    assert payload["book_count"] == 1
    assert cache.set_calls
    assert client.closed is True


@pytest.mark.asyncio
async def test_series_continuity_check_handles_no_prior_books_and_full_review(monkeypatch):
    series_id = uuid.uuid4()
    book_id = uuid.uuid4()
    prior_id = uuid.uuid4()
    user_id = uuid.uuid4()
    series = SimpleNamespace(id=series_id, user_id=user_id, name="Atlas Saga")
    current_book = SimpleNamespace(id=book_id, user_id=user_id, title="Book Two")
    cache = _Cache()
    monkeypatch.setattr(advisor, "advisor_response_cache", cache)
    monkeypatch.setattr(advisor, "make_editorial_cache_key", lambda *_args: "series-cont-key")

    body = advisor.SeriesContinuityRequest(
        messages=[AdvisorMessage(role="user", content="Check this")],
        total_chapters=10,
        book_id=book_id,
        chapter_num=5,
        text="New passage",
    )

    db = _FakeDB(
        get_values=[series, current_book],
        execute_values=[_Result(all_rows=[SimpleNamespace(book_id=book_id, position=1)])],
    )
    payload = await advisor.series_continuity_check(
        series_id,
        body=body,
        db=db,
        current_user=SimpleNamespace(id=user_id),
        _=None,
    )
    assert "first book in the series" in payload["review"]["overall_verdict"].lower()

    client = _FakeClient('{"overall_verdict":"Looks aligned"}')
    async def _fake_story_context(*_args, **_kwargs):
        return "Series context"

    async def _fake_embed_text(_text):
        return [0.4, 0.2]

    monkeypatch.setattr(advisor, "build_series_story_context", _fake_story_context)
    monkeypatch.setattr(advisor, "embed_text", _fake_embed_text)
    monkeypatch.setattr(advisor, "normalize_series_continuity_result", lambda raw: {"overall_verdict": raw})
    monkeypatch.setattr(advisor, "AsyncOpenAI", lambda api_key: client)
    db = _FakeDB(
        get_values=[series, current_book],
        execute_values=[
            _Result(all_rows=[SimpleNamespace(book_id=prior_id, position=1), SimpleNamespace(book_id=book_id, position=2)]),
            _Result(all_rows=[SimpleNamespace(id=prior_id, title="Book One")]),
            _Result(fetchall_rows=[SimpleNamespace(text="Earlier clue", chapter_num=4, chapter_title="Vault", book_title="Book One", relevance=0.8)]),
        ],
    )

    payload = await advisor.series_continuity_check(
        series_id,
        body=body,
        db=db,
        current_user=SimpleNamespace(id=user_id),
        _=None,
    )

    assert payload["review"]["overall_verdict"].startswith("{")
    assert payload["retrieved_passages"][0]["book_title"] == "Book One"
    assert cache.set_calls
    assert client.closed is True
