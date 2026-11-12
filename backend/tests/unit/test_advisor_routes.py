from __future__ import annotations

import asyncio
import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.responses import Response
from pydantic import ValidationError

from app.schemas.advisor import (
    AdvisorMessage,
    AdvisorRequest,
    EditorialReviewRequest,
    InlineContinuityRequest,
    ProseTightenRequest,
    VoiceConsistencyRequest,
    WhatsTheWordRequest,
)
from app.utils import advisor_scan_utils as advisor_scan_utils_module
from tests.unit.route_facades import advisor
from tests.unit.route_patch_helpers import patch_route_dependency


@pytest.fixture(autouse=True)
def _stub_llm_reservation_lifecycle(monkeypatch):
    async def reserve(**kwargs):
        return SimpleNamespace(
            id="test-reservation", operation=kwargs["operation"], user_id=kwargs["user_id"]
        )

    async def finish(*_args, **_kwargs):
        return None

    monkeypatch.setattr("app.services.llm_control_service.reserve_llm_call", reserve)
    monkeypatch.setattr("app.services.llm_control_service.finish_llm_reservation", finish)
    monkeypatch.setattr("app.services.llm_control_service.fail_llm_reservation", finish)


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
        self.added = []
        self.commits = 0
        self.statements = []

    async def get(self, *_args, **_kwargs):
        return self._get_values.pop(0)

    async def execute(self, *_args, **_kwargs):
        self.statements.append(_args[0])
        return self._execute_values.pop(0)

    def add(self, value):
        self.added.append(value)

    async def commit(self):
        self.commits += 1

    async def refresh(self, _value):
        return None


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
            choices=[
                SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content=content))
            ]
        )

    async def close(self):
        self.closed = True


class _AsyncCache:
    def __init__(self, data=None):
        self.data = dict(data or {})
        self.set_calls = []

    async def get(self, *key_parts, **_kwargs):
        return self.data.get(tuple(str(part) for part in key_parts))

    async def set(self, *key_parts_and_value, **_kwargs):
        *key_parts, value = key_parts_and_value
        key = tuple(str(part) for part in key_parts)
        self.data[key] = value
        self.set_calls.append((key, value))


def _patch_route_caches(monkeypatch, cache: _AsyncCache) -> None:
    async def cache_version(*_args, **_kwargs):
        return 0

    patch_route_dependency(monkeypatch, advisor, "get_book_cache_version", cache_version)
    patch_route_dependency(monkeypatch, advisor, "get_series_cache_version", cache_version)
    patch_route_dependency(monkeypatch, advisor, "get_advisor_response_cache", cache.get)
    patch_route_dependency(monkeypatch, advisor, "set_advisor_response_cache", cache.set)
    patch_route_dependency(monkeypatch, advisor, "get_editorial_review_cache", cache.get)
    patch_route_dependency(monkeypatch, advisor, "set_editorial_review_cache", cache.set)
    patch_route_dependency(monkeypatch, advisor, "get_proactive_scan_cache", cache.get)
    patch_route_dependency(monkeypatch, advisor, "set_proactive_scan_cache", cache.set)
    monkeypatch.setattr(advisor_scan_utils_module, "get_proactive_scan_cache", cache.get)
    monkeypatch.setattr(advisor_scan_utils_module, "set_proactive_scan_cache", cache.set)
    patch_route_dependency(monkeypatch, advisor, "get_prose_tighten_cache", cache.get)
    patch_route_dependency(monkeypatch, advisor, "set_prose_tighten_cache", cache.set)
    patch_route_dependency(monkeypatch, advisor, "get_voice_consistency_cache", cache.get)
    patch_route_dependency(monkeypatch, advisor, "set_voice_consistency_cache", cache.set)
    patch_route_dependency(monkeypatch, advisor, "get_series_advisor_response_cache", cache.get)
    patch_route_dependency(monkeypatch, advisor, "set_series_advisor_response_cache", cache.set)
    patch_route_dependency(monkeypatch, advisor, "get_series_continuity_cache", cache.get)
    patch_route_dependency(monkeypatch, advisor, "set_series_continuity_cache", cache.set)


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
    assert (
        advisor._best_issue_snippet(text, description)
        == "The silver key disappears during the storm."
    )
    assert advisor._best_issue_snippet("No punctuation here", "missing") == "No punctuation here"


def test_whats_the_word_request_requires_enough_description_words():
    with pytest.raises(ValidationError):
        WhatsTheWordRequest(description="too vague right now")

    payload = WhatsTheWordRequest(
        description="a smile that hides contempt behind politeness",
        previous_word="smirk",
    )

    assert payload.description == "a smile that hides contempt behind politeness"
    assert payload.previous_word == "smirk"


@pytest.mark.asyncio
async def test_advisor_message_validates_book_and_messages():
    db = _FakeDB(get_values=[None])
    body = _message_body(("user", "Help"))
    with pytest.raises(HTTPException) as exc:
        await advisor.advisor_message(
            uuid.uuid4(),
            body=body,
            response=Response(),
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
            response=Response(),
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
            response=Response(),
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
    cache = _AsyncCache({(str(book_id), "cached-key"): {"reply": "Cached", "intent": "direction"}})
    patch_route_dependency(
        monkeypatch, advisor, "make_advisor_cache_key", lambda *_args: "cached-key"
    )
    _patch_route_caches(monkeypatch, cache)
    db = _FakeDB(get_values=[book])

    payload = await advisor.advisor_message(
        book_id,
        body=_message_body(("user", "What next?")),
        response=Response(),
        db=db,
        current_user=SimpleNamespace(id=user_id),
        _=None,
    )

    assert payload["reply"] == "Cached"
    assert payload["cached"] is True


@pytest.mark.asyncio
async def test_advisor_message_enqueues_task_when_not_cached(monkeypatch):
    book_id = uuid.uuid4()
    user_id = uuid.uuid4()
    book = SimpleNamespace(id=book_id, user_id=user_id, title="Atlas", total_chapters=8)
    cache = _AsyncCache()
    db = _FakeDB(get_values=[book])
    captured: dict[str, object] = {}
    job_id = uuid.uuid4()

    class _Task:
        def apply_async(self, *, task_id, kwargs):
            captured["task_id"] = task_id
            captured["kwargs"] = kwargs

    async def _fake_create_job(*_args, **_kwargs):
        return SimpleNamespace(id=job_id)

    patch_route_dependency(
        monkeypatch, advisor, "make_advisor_cache_key", lambda *_args: "queued-key"
    )
    _patch_route_caches(monkeypatch, cache)
    patch_route_dependency(monkeypatch, advisor, "generate_advisor_reply_task", _Task())
    patch_route_dependency(monkeypatch, advisor, "create_advisor_job", _fake_create_job)

    response = Response()
    payload = await advisor.advisor_message(
        book_id,
        body=_message_body(("user", "What next?")),
        response=response,
        db=db,
        current_user=SimpleNamespace(id=user_id),
        _=None,
    )

    assert response.status_code == 202
    assert payload == {"task_id": str(job_id), "status": "queued", "cached": False}
    assert captured["task_id"] == str(job_id)


@pytest.mark.asyncio
async def test_advisor_message_marks_job_failed_when_enqueue_fails(monkeypatch):
    book_id = uuid.uuid4()
    user_id = uuid.uuid4()
    book = SimpleNamespace(id=book_id, user_id=user_id, title="Atlas", total_chapters=8)
    cache = _AsyncCache()
    db = _FakeDB(get_values=[book])
    job_id = uuid.uuid4()
    failed: dict[str, object] = {}

    class _Task:
        def apply_async(self, *, task_id, kwargs):
            raise RuntimeError("broker unavailable")

    async def _fake_create_job(*_args, **_kwargs):
        return SimpleNamespace(id=job_id)

    async def _fake_mark_failed(*_args, **kwargs):
        failed.update(kwargs)

    patch_route_dependency(
        monkeypatch, advisor, "make_advisor_cache_key", lambda *_args: "queued-key"
    )
    _patch_route_caches(monkeypatch, cache)
    patch_route_dependency(monkeypatch, advisor, "generate_advisor_reply_task", _Task())
    patch_route_dependency(monkeypatch, advisor, "create_advisor_job", _fake_create_job)
    patch_route_dependency(monkeypatch, advisor, "mark_advisor_job_failed", _fake_mark_failed)

    with pytest.raises(RuntimeError, match="broker unavailable"):
        await advisor.advisor_message(
            book_id,
            body=_message_body(("user", "What next?")),
            response=Response(),
            db=db,
            current_user=SimpleNamespace(id=user_id),
            _=None,
        )

    assert failed["job_id"] == job_id
    assert failed["error_code"] == "advisor_enqueue_failed"


@pytest.mark.asyncio
async def test_advisor_message_async_uses_stored_book_chapter_count(monkeypatch):
    book_id = uuid.uuid4()
    user_id = uuid.uuid4()
    book = SimpleNamespace(id=book_id, user_id=user_id, title="Atlas {Saga}", total_chapters=12)
    db = _FakeDB(get_values=[book])
    cache = _AsyncCache()
    captured: dict[str, object] = {}
    job_id = uuid.uuid4()

    class _Task:
        def apply_async(self, *, task_id, kwargs):
            captured["task_id"] = task_id
            captured["kwargs"] = kwargs

    async def _fake_create_job(*_args, **_kwargs):
        return SimpleNamespace(id=job_id)

    patch_route_dependency(
        monkeypatch, advisor, "make_advisor_cache_key", lambda *_args: "advisor-key"
    )
    _patch_route_caches(monkeypatch, cache)
    patch_route_dependency(monkeypatch, advisor, "generate_advisor_reply_task", _Task())
    patch_route_dependency(monkeypatch, advisor, "create_advisor_job", _fake_create_job)

    response = Response()
    payload = await advisor.advisor_message_async(
        book_id,
        body=_message_body(
            ("assistant", "Context"), ("user", "Check the storm lore"), total_chapters=8
        ),
        response=response,
        db=db,
        current_user=SimpleNamespace(id=user_id),
        _=None,
    )

    assert response.status_code == 202
    assert payload == {"task_id": str(job_id), "status": "queued", "cached": False}
    assert captured["task_id"] == str(job_id)
    assert captured["kwargs"] == {
        "job_id": str(job_id),
        "book_id": str(book_id),
        "user_id": str(user_id),
        "messages": [
            {"role": "assistant", "content": "Context"},
            {"role": "user", "content": "Check the storm lore"},
        ],
        "total_chapters": 12,
    }


@pytest.mark.asyncio
async def test_advisor_message_async_status_returns_completed_payload(monkeypatch):
    book_id = uuid.uuid4()
    user_id = uuid.uuid4()
    book = SimpleNamespace(id=book_id, user_id=user_id, title="Atlas", total_chapters=12)
    job_id = uuid.uuid4()
    job = SimpleNamespace(
        id=job_id,
        user_id=user_id,
        scope="book",
        book_id=book_id,
        status="complete",
        result_json={
            "reply": "Advisor reply",
            "intent": "general",
            "response_type": "standard",
            "retrieved_passages": [],
        },
        error_code=None,
    )
    db = _FakeDB(get_values=[book, job])

    payload = await advisor.advisor_message_async_status(
        book_id,
        str(job_id),
        db=db,
        current_user=SimpleNamespace(id=user_id),
    )

    assert payload["status"] == "complete"
    assert payload["result"]["reply"] == "Advisor reply"


@pytest.mark.asyncio
async def test_advisor_message_stream_hides_internal_errors(monkeypatch):
    user_id = uuid.uuid4()
    book = SimpleNamespace(id=uuid.uuid4(), user_id=user_id, title="Atlas", total_chapters=8)
    db = _FakeDB(get_values=[book])

    async def _fake_stream_advisor_reply_payload(**_kwargs):
        raise RuntimeError("openai_api_key=sk-secret")
        yield

    patch_route_dependency(
        monkeypatch, advisor, "stream_advisor_reply_payload", _fake_stream_advisor_reply_payload
    )

    response = await advisor.advisor_message_stream(
        book.id,
        body=_message_body(("user", "Help")),
        db=db,
        current_user=SimpleNamespace(id=user_id),
        _=None,
    )
    body = "".join([chunk async for chunk in response.body_iterator])

    assert "Something went wrong. Please try again." in body
    assert "sk-secret" not in body


@pytest.mark.asyncio
async def test_advisor_message_stream_returns_llm_token_limit_as_sse_error(monkeypatch):
    user_id = uuid.uuid4()
    book = SimpleNamespace(id=uuid.uuid4(), user_id=user_id, title="Atlas", total_chapters=8)
    db = _FakeDB(get_values=[book])

    async def _fake_stream_advisor_reply_payload(**_kwargs):
        raise HTTPException(
            429,
            {
                "kind": "llm_tokens",
                "message": "LLM usage token limit exceeded for the 5-hour window.",
            },
        )
        yield

    patch_route_dependency(
        monkeypatch, advisor, "stream_advisor_reply_payload", _fake_stream_advisor_reply_payload
    )

    response = await advisor.advisor_message_stream(
        book.id,
        body=_message_body(("user", "Help")),
        db=db,
        current_user=SimpleNamespace(id=user_id),
        _=None,
    )
    body = "".join([chunk async for chunk in response.body_iterator])

    assert "event: error" in body
    assert "LLM usage token limit exceeded for the 5-hour window." in body


@pytest.mark.asyncio
async def test_advisor_greeting_counts_entities():
    book_id = uuid.uuid4()
    user_id = uuid.uuid4()
    book = SimpleNamespace(id=book_id, user_id=user_id, title="Atlas", total_chapters=11)
    db = _FakeDB(
        get_values=[book],
        execute_values=[_Result(scalar_one=4), _Result(scalar_one=9)],
    )

    payload = await advisor.advisor_greeting(
        book_id, db=db, current_user=SimpleNamespace(id=user_id)
    )

    assert payload["book_title"] == "Atlas"
    assert payload["stats"] == {"characters": 9, "plot_threads": 4, "total_chapters": 11}


@pytest.mark.asyncio
async def test_whats_the_word_validates_book_and_returns_result(monkeypatch):
    book_id = uuid.uuid4()
    user_id = uuid.uuid4()
    book = SimpleNamespace(id=book_id, user_id=user_id, title="Atlas")
    db = _FakeDB(get_values=[book])
    client = _FakeClient('{"word":"acerbic","gloss":"sharp with cutting contempt"}')

    async def _fake_generate(**kwargs):
        assert kwargs["book_title"] == "Atlas"
        assert kwargs["description"] == "a smile that hides contempt behind politeness"
        assert kwargs["previous_word"] == "smirk"
        return {"word": "acerbic", "gloss": "sharp with cutting contempt"}

    patch_route_dependency(monkeypatch, advisor, "AsyncOpenAI", lambda **_kwargs: client)
    patch_route_dependency(monkeypatch, advisor, "generate_whats_the_word_result", _fake_generate)

    payload = await advisor.whats_the_word(
        book_id,
        body=WhatsTheWordRequest(
            description="a smile that hides contempt behind politeness",
            previous_word="smirk",
        ),
        db=db,
        current_user=SimpleNamespace(id=user_id),
        _=None,
    )

    assert payload.word == "acerbic"
    assert payload.gloss == "sharp with cutting contempt"
    assert client.closed is False


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
        last_mentioned_at=4,
        resolved_at=None,
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
        ([{"clue": "Rust key", "foreshadows": "A hidden vault"}], 4, "Vault"),
        ({"one": "Hidden map"}, 5, "Tunnel"),
    ]
    lead_character = SimpleNamespace(id=char_id, name="Iris", mention_count=12, first_chapter=1)
    db = _FakeDB(
        get_values=[book],
        execute_values=[
            _Result(scalars=[lead_character, absent, underused]),
            _Result(scalars=[dropped]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(all_rows=states),
            _Result(scalars=[dropped]),
            _Result(scalars=[absent]),
            _Result(scalars=[dropped]),
            _Result(scalars=[dropped]),
            _Result(scalars=[underused]),
            _Result(all_rows=recent_summaries),
            _Result(all_rows=[]),
        ],
    )

    payload = await advisor.advisor_suggestions(
        book_id, db=db, current_user=SimpleNamespace(id=user_id)
    )

    assert payload["total"] >= 6
    types = [item["type"] for item in payload["suggestions"]]
    assert "trait_contradiction" in types
    assert "dropped_thread" in types
    assert "character_absent" in types
    assert "arc_opportunity" in types
    assert "foreshadowing_opportunity" in types
    assert "clue_review" in types
    clue_review = next(item for item in payload["suggestions"] if item["type"] == "clue_review")
    assert "Review possible clue" in clue_review["title"]
    assert '"Rust key"' in clue_review["description"]
    assert "A hidden vault" not in clue_review["description"]
    assert "Check the manuscript and later chapters" in clue_review["description"]
    assert "plothole" not in clue_review["description"]
    assert payload["meta"]["character_count"] == 3
    assert payload["meta"]["open_thread_count"] == 1
    assert payload["meta"]["fallback_applied"] is False
    assert payload["meta"]["proactive_audit_applied"] is False
    severities = [item["severity"] for item in payload["suggestions"]]
    assert severities == sorted(
        severities,
        key=lambda item: {"warning": 0, "direction": 1, "opportunity": 2, "info": 3}.get(item, 4),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("include_author", [False, True])
async def test_advisor_uses_only_supported_relationships_as_evidence(include_author):
    book_id = uuid.uuid4()
    user_id = uuid.uuid4()
    character_a_id = uuid.uuid4()
    character_b_id = uuid.uuid4()
    book = SimpleNamespace(id=book_id, user_id=user_id, title="Atlas", total_chapters=3)
    characters = [
        SimpleNamespace(id=character_a_id, name="Mara"),
        SimpleNamespace(id=character_b_id, name="Ilan"),
    ]
    unverified = SimpleNamespace(
        character_a_id=character_a_id,
        character_b_id=character_b_id,
        rel_type="friend",
        sentiment=0.5,
        from_chapter=2,
        description="They met.",
        edited_by_author=False,
        label_evidence={},
    )
    relationships = [unverified]
    if include_author:
        relationships.append(SimpleNamespace(**{**vars(unverified), "edited_by_author": True}))
    db = _FakeDB(
        execute_values=[
            _Result(scalars=characters),
            _Result(scalars=[]),
            _Result(scalars=relationships),
            _Result(scalars=[]),
            _Result(all_rows=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(all_rows=[]),
            _Result(all_rows=[]),
        ],
    )

    payload = await advisor_scan_utils_module.build_advisor_suggestions_payload(
        db=db, book=book, user_id=user_id, skip_llm=True
    )

    assert payload["meta"]["relationship_count"] == int(include_author)
    assert ("relationships" in payload["meta"]["scan_basis"]) is include_author
    assert ("verified relationships" in payload["meta"]["data_gaps"]) is not include_author


@pytest.mark.asyncio
async def test_advisor_suggestions_does_not_invent_findings_when_evidence_is_empty():
    book_id = uuid.uuid4()
    user_id = uuid.uuid4()
    book = SimpleNamespace(id=book_id, user_id=user_id, title="Atlas", total_chapters=5)
    db = _FakeDB(
        get_values=[book],
        execute_values=[
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(all_rows=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(all_rows=[]),
            _Result(all_rows=[]),
        ],
    )

    payload = await advisor.advisor_suggestions(
        book_id, db=db, current_user=SimpleNamespace(id=user_id)
    )

    assert payload["total"] == 0
    assert payload["suggestions"] == []
    assert payload["meta"]["fallback_applied"] is False
    assert payload["meta"]["proactive_audit_applied"] is False
    assert "characters" in payload["meta"]["data_gaps"]
    assert "plot threads" in payload["meta"]["data_gaps"]


@pytest.mark.asyncio
async def test_advisor_suggestions_show_every_stored_contradicted_thread_without_an_ai_audit():
    book_id = uuid.uuid4()
    user_id = uuid.uuid4()
    book = SimpleNamespace(id=book_id, user_id=user_id, title="Atlas", total_chapters=5)
    threads = [
        SimpleNamespace(
            id=uuid.uuid4(),
            title=f"Promise {index}",
            status="contradicted",
            introduced_at=1,
            last_mentioned_at=3,
            resolved_at=None,
            description=f"Promise {index} was contradicted.",
            importance=8,
        )
        for index in range(3)
    ]
    db = _FakeDB(
        execute_values=[
            _Result(scalars=[]),
            _Result(scalars=threads),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(all_rows=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(all_rows=[]),
        ]
    )

    payload = await advisor_scan_utils_module.build_advisor_suggestions_payload(
        db=db, book=book, user_id=user_id, skip_llm=True
    )

    assert {item["id"] for item in payload["suggestions"]} == {
        f"contradicted-{thread.id}" for thread in threads
    }
    assert payload["meta"]["heuristic_count"] == 3
    assert payload["meta"]["proactive_audit_applied"] is False


@pytest.mark.asyncio
async def test_advisor_suggestions_count_detailed_clues_beyond_first_ten_chapters():
    book_id = uuid.uuid4()
    user_id = uuid.uuid4()
    book = SimpleNamespace(id=book_id, user_id=user_id, title="Atlas", total_chapters=12)
    db = _FakeDB(
        execute_values=[
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(all_rows=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(
                all_rows=[
                    (
                        [{"clue": f"Clue {number}", "why_it_matters": "Watch this detail"}],
                        number,
                        f"Chapter {number}",
                    )
                    for number in range(1, 13)
                ]
            ),
        ]
    )

    payload = await advisor_scan_utils_module.build_advisor_suggestions_payload(
        db=db, book=book, user_id=user_id, skip_llm=True
    )

    clue_statement = next(
        statement for statement in db.statements if "chapter_summaries.clues" in str(statement)
    )
    assert "detailed" in clue_statement.compile().params.values()
    assert payload["meta"]["clue_count"] == 12
    assert "chapter summaries" in payload["meta"]["scan_basis"]
    assert len(payload["suggestions"]) == 3
    assert all("{'clue':" not in item["description"] for item in payload["suggestions"])


@pytest.mark.asyncio
@pytest.mark.parametrize("cached", [True, False])
async def test_recommended_checks_page_load_uses_cached_audit_without_new_model_calls(
    monkeypatch, cached
):
    book_id = uuid.uuid4()
    user_id = uuid.uuid4()
    book = SimpleNamespace(id=book_id, user_id=user_id, title="Atlas", total_chapters=2)
    cache = _AsyncCache()
    if cached:
        cache.data[(str(book_id), "scan-cache")] = {
            "findings": [
                {
                    "severity": "warning",
                    "type": "event_conflict",
                    "title": "Gate timing",
                    "description": "The gate closes early.",
                    "evidence_excerpt": "The gate closes.",
                    "chapter_ref": 2,
                    "action_label": "Check timing",
                    "ask_prompt": "When did it close?",
                }
            ],
            "overall_note": "One supported check.",
        }

    async def cache_version(*_args, **_kwargs):
        return 0

    def forbidden_model_call():
        raise AssertionError("A page load must not start a paid AI audit")

    _patch_route_caches(monkeypatch, cache)
    monkeypatch.setattr(advisor_scan_utils_module, "get_book_cache_version", cache_version)
    monkeypatch.setattr(advisor_scan_utils_module, "get_openai_client", forbidden_model_call)
    monkeypatch.setattr(advisor.settings, "OPENAI_API_KEY", "test-key", raising=False)
    monkeypatch.setattr(advisor.settings, "OPENAI_INTEL_MODEL", "gpt-test", raising=False)
    monkeypatch.setattr(
        advisor_scan_utils_module, "make_editorial_cache_key", lambda *_args: "scan-cache"
    )
    db = _FakeDB(
        get_values=[book],
        execute_values=[
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(all_rows=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(all_rows=[([], 2, "Ending")]),
            _Result(all_rows=[(2, "Ending", "The gate closes.", [])]),
        ],
    )

    payload = await advisor.advisor_suggestions(
        book_id, db=db, current_user=SimpleNamespace(id=user_id)
    )

    assert payload["total"] == (1 if cached else 0)
    assert payload["meta"]["proactive_audit_applied"] is cached
    assert payload["meta"]["audit_groups_total"] == 1
    assert payload["meta"]["audit_groups_completed"] == int(cached)
    if not cached:
        assert "Refresh checks" in payload["meta"]["audit_summary"]
    assert db.commits == 0


@pytest.mark.asyncio
async def test_unconfigured_advisor_refresh_keeps_later_cached_groups(monkeypatch):
    book_id = uuid.uuid4()
    user_id = uuid.uuid4()
    book = SimpleNamespace(id=book_id, user_id=user_id, title="Atlas", total_chapters=2)
    cache = _AsyncCache(
        {
            (str(book_id), "scan-cached"): {
                "findings": [],
                "overall_note": "Cached group reviewed.",
            }
        }
    )
    _patch_route_caches(monkeypatch, cache)
    monkeypatch.setattr(advisor.settings, "OPENAI_API_KEY", "", raising=False)
    monkeypatch.setattr(advisor.settings, "OPENAI_INTEL_MODEL", "", raising=False)
    monkeypatch.setattr(
        advisor_scan_utils_module,
        "partition_advisor_scan_evidence",
        lambda **_kwargs: [
            {
                "summaries": ["Uncached evidence"],
                "threads": [],
                "relationships": [],
                "world_elements": [],
            },
            {
                "summaries": ["Cached evidence"],
                "threads": [],
                "relationships": [],
                "world_elements": [],
            },
        ],
    )
    monkeypatch.setattr(
        advisor_scan_utils_module,
        "make_editorial_cache_key",
        lambda _scope, evidence, _count: (
            "scan-cached" if "Cached evidence" in evidence else "scan-uncached"
        ),
    )
    db = _FakeDB(
        execute_values=[
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(all_rows=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(all_rows=[]),
            _Result(all_rows=[]),
        ]
    )

    payload = await advisor_scan_utils_module.build_advisor_suggestions_payload(
        db=db, book=book, user_id=user_id, force_audit=True
    )

    assert payload["meta"]["audit_groups_total"] == 2
    assert payload["meta"]["audit_groups_completed"] == 1
    assert payload["meta"]["proactive_audit_applied"] is True
    assert payload["meta"]["audit_failure_category"] == "not_configured"
    assert "1 of 2" in payload["meta"]["audit_summary"]
    assert db.commits == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid_cache_kind",
    ["partial", "fabricated_evidence", "wrong_chapter", "malformed_shape"],
)
async def test_recommended_checks_rejects_invalid_cached_audit_without_paid_scan(
    monkeypatch, invalid_cache_kind
):
    book_id = uuid.uuid4()
    user_id = uuid.uuid4()
    book = SimpleNamespace(id=book_id, user_id=user_id, title="Atlas", total_chapters=2)
    finding = {
        "severity": "warning",
        "type": "event_conflict",
        "title": "Gate timing",
        "description": "The gate closes early.",
        "evidence_excerpt": "The gate closes.",
        "chapter_ref": 2,
        "action_label": "Check timing",
        "ask_prompt": "When did it close?",
    }
    cached_result = {"findings": [finding], "overall_note": "One supported check."}
    if invalid_cache_kind == "partial":
        cached_result["partial"] = True
    elif invalid_cache_kind == "fabricated_evidence":
        finding["evidence_excerpt"] = "The gate was made of crystal."
    elif invalid_cache_kind == "wrong_chapter":
        finding["chapter_ref"] = 999
    else:
        cached_result["findings"] = "not a list"
    cache = _AsyncCache({(str(book_id), "scan-cache"): cached_result})

    def forbidden_model_call():
        raise AssertionError("A page load must not start a paid AI audit")

    _patch_route_caches(monkeypatch, cache)
    monkeypatch.setattr(advisor_scan_utils_module, "get_openai_client", forbidden_model_call)
    monkeypatch.setattr(
        advisor_scan_utils_module, "make_editorial_cache_key", lambda *_args: "scan-cache"
    )
    db = _FakeDB(
        get_values=[book],
        execute_values=[
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(all_rows=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(all_rows=[([], 2, "Ending")]),
            _Result(all_rows=[(2, "Ending", "The gate closes.", [])]),
        ],
    )

    payload = await advisor.advisor_suggestions(
        book_id, db=db, current_user=SimpleNamespace(id=user_id)
    )

    assert payload["total"] == 0
    assert payload["meta"]["audit_groups_total"] == 1
    assert payload["meta"]["audit_groups_completed"] == 0
    assert payload["meta"]["proactive_audit_applied"] is False
    assert payload["meta"]["audit_failure_category"] == "invalid_ai_response"
    assert cache.set_calls == []
    assert db.commits == 0


@pytest.mark.asyncio
async def test_refresh_replaces_invalid_cached_audit_with_verified_result(monkeypatch):
    book_id = uuid.uuid4()
    user_id = uuid.uuid4()
    book = SimpleNamespace(id=book_id, user_id=user_id, title="Atlas", total_chapters=2)
    cache = _AsyncCache(
        {
            (str(book_id), "scan-cache"): {
                "findings": [{"title": "Unsupported finding"}],
                "overall_note": "Unverified check.",
            }
        }
    )
    scan_calls = []

    async def fake_story_context(*_args, **_kwargs):
        return "Story context"

    async def fake_scan(**kwargs):
        scan_calls.append(kwargs["source_blocks"])
        return {
            "findings": [
                {
                    "severity": "warning",
                    "type": "event_conflict",
                    "title": "Gate timing",
                    "description": "The gate closes early.",
                    "evidence_excerpt": "The gate closes.",
                    "chapter_ref": 2,
                    "action_label": "Check timing",
                    "ask_prompt": "When did it close?",
                }
            ],
            "overall_note": "One supported check.",
        }

    _patch_route_caches(monkeypatch, cache)
    monkeypatch.setattr(advisor_scan_utils_module, "get_openai_client", lambda: object())
    monkeypatch.setattr(advisor_scan_utils_module, "build_story_context", fake_story_context)
    monkeypatch.setattr(advisor_scan_utils_module, "request_proactive_scan_result", fake_scan)
    monkeypatch.setattr(
        advisor_scan_utils_module, "make_editorial_cache_key", lambda *_args: "scan-cache"
    )
    monkeypatch.setattr(advisor.settings, "OPENAI_API_KEY", "test-key", raising=False)
    monkeypatch.setattr(advisor.settings, "OPENAI_INTEL_MODEL", "gpt-test", raising=False)
    db = _FakeDB(
        execute_values=[
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(all_rows=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(all_rows=[([], 2, "Ending")]),
            _Result(all_rows=[(2, "Ending", "The gate closes.", [])]),
        ],
    )

    payload = await advisor_scan_utils_module.build_advisor_suggestions_payload(
        db=db, book=book, user_id=user_id, force_audit=True
    )

    assert len(scan_calls) == 1
    assert payload["meta"]["audit_groups_completed"] == 1
    assert payload["meta"]["audit_failure_category"] is None
    assert [item["title"] for item in payload["suggestions"]] == ["Gate timing"]
    assert len(cache.set_calls) == 1
    assert db.commits == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("evidence_kind", ["summary_without_clues", "relationship_only"])
async def test_recommended_checks_include_groups_without_clues_or_threads(
    monkeypatch, evidence_kind
):
    book_id = uuid.uuid4()
    user_id = uuid.uuid4()
    book = SimpleNamespace(id=book_id, user_id=user_id, title="Atlas", total_chapters=2)
    cache = _AsyncCache()
    cache.data[(str(book_id), "scan-cache")] = {
        "findings": [],
        "overall_note": "No supported checks found.",
    }

    async def cache_version(*_args, **_kwargs):
        return 0

    _patch_route_caches(monkeypatch, cache)
    monkeypatch.setattr(advisor_scan_utils_module, "get_book_cache_version", cache_version)
    monkeypatch.setattr(
        advisor_scan_utils_module, "make_editorial_cache_key", lambda *_args: "scan-cache"
    )
    relationship = SimpleNamespace(
        id=uuid.uuid4(),
        character_a_id=uuid.uuid4(),
        character_b_id=uuid.uuid4(),
        rel_type="ally",
        from_chapter=1,
        description="The wardens work together.",
        sentiment=0.5,
        edited_by_author=True,
    )
    db = _FakeDB(
        get_values=[book],
        execute_values=[
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(scalars=[relationship] if evidence_kind == "relationship_only" else []),
            _Result(scalars=[]),
            _Result(all_rows=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(all_rows=[]),
            _Result(
                all_rows=[(2, "Ending", "The final gate closes.", [])]
                if evidence_kind == "summary_without_clues"
                else []
            ),
        ],
    )

    payload = await advisor.advisor_suggestions(
        book_id, db=db, current_user=SimpleNamespace(id=user_id)
    )

    assert payload["meta"]["audit_groups_total"] == 1
    assert payload["meta"]["audit_groups_completed"] == 1
    assert payload["meta"]["proactive_audit_applied"] is True
    assert payload["meta"]["audit_failure_category"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize("distinct_evidence", [False, True])
async def test_proactive_check_dedupes_shared_evidence_but_keeps_distinct_checks(
    monkeypatch, distinct_evidence
):
    book_id = uuid.uuid4()
    user_id = uuid.uuid4()
    book = SimpleNamespace(id=book_id, user_id=user_id, title="Atlas", total_chapters=5)
    cache = _AsyncCache()
    finding = {
        "severity": "warning",
        "type": "event_conflict",
        "title": "Gate timing",
        "description": "The gate timing may conflict.",
        "evidence_excerpt": "The gate closes before the travelers arrive.",
        "chapter_ref": 2,
        "action_label": "Check timing",
        "ask_prompt": "When did the gate close?",
    }
    scan_calls = []

    async def fake_story_context(*_args, **_kwargs):
        return "Story context"

    async def fake_scan(**kwargs):
        scan_calls.append(kwargs["source_blocks"])
        if distinct_evidence:
            chapter = 5 if len(scan_calls) == 1 else 1
            current = {
                **finding,
                "evidence_excerpt": f"Chapter {chapter} event.",
                "chapter_ref": chapter,
            }
        else:
            current = {**finding, "title": f"Gate check {len(scan_calls)}"}
        return {
            "findings": [current],
            "overall_note": "Review gate timing.",
        }

    _patch_route_caches(monkeypatch, cache)
    monkeypatch.setattr(advisor_scan_utils_module, "get_openai_client", lambda: object())
    monkeypatch.setattr(advisor_scan_utils_module, "build_story_context", fake_story_context)
    monkeypatch.setattr(advisor_scan_utils_module, "request_proactive_scan_result", fake_scan)
    monkeypatch.setattr(advisor.settings, "OPENAI_API_KEY", "test-key", raising=False)
    monkeypatch.setattr(advisor.settings, "OPENAI_INTEL_MODEL", "gpt-test", raising=False)
    db = _FakeDB(
        execute_values=[
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(all_rows=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(all_rows=[]),
            _Result(
                all_rows=[
                    (
                        chapter,
                        f"Chapter {chapter}",
                        finding["evidence_excerpt"]
                        if chapter == 2
                        else f"Chapter {chapter} event.",
                        [],
                    )
                    for chapter in range(5, 0, -1)
                ]
            ),
        ],
    )

    payload = await advisor_scan_utils_module.build_advisor_suggestions_payload(
        db=db, book=book, user_id=user_id, force_audit=True
    )

    assert len(scan_calls) == 2
    if distinct_evidence:
        assert "Chapter 5 event." in " ".join(scan_calls[0])
        assert "Chapter 1 event." in " ".join(scan_calls[1])
    else:
        assert all(finding["evidence_excerpt"] in " ".join(blocks) for blocks in scan_calls)
    assert payload["meta"]["audit_groups_completed"] == 2
    assert len(payload["suggestions"]) == (2 if distinct_evidence else 1)
    assert all(item["id"].startswith("proactive-") for item in payload["suggestions"])


@pytest.mark.asyncio
@pytest.mark.parametrize("second_group_valid", [True, False])
async def test_advisor_suggestions_runs_proactive_audit_even_with_multiple_heuristics(
    monkeypatch, second_group_valid
):
    book_id = uuid.uuid4()
    user_id = uuid.uuid4()
    book = SimpleNamespace(id=book_id, user_id=user_id, title="Atlas", total_chapters=12)
    cache = _AsyncCache()
    client = _FakeClient(
        '{"findings":[{"severity":"direction","type":"future_direction","title":"Audit thread pressure point","description":"The ferryman bargain needs a clearer payoff path before the finale.","evidence_excerpt":"The ferryman bargain remains unresolved after the crossing.","chapter_ref":9,"action_label":"Plan the payoff","ask_prompt":"How should the ferryman bargain resolve?"}],"overall_note":"First evidence group reviewed."}',
        '{"findings":[{"severity":"warning","type":"event_conflict","title":"Gate timing","description":"The gate is locked before the arrival in chapter 5.","evidence_excerpt":"The gate was locked before the travelers arrived.","chapter_ref":5,"action_label":"Check timing","ask_prompt":"When was the gate locked?"}],"overall_note":"Second evidence group reviewed."}'
        if second_group_valid
        else "not-json",
        *([] if second_group_valid else ["not-json"]),
        '{"findings":[],"overall_note":"Sparse heuristics triggered a deeper audit."}',
    )

    async def _fake_story_context(*_args, **_kwargs):
        return "Story context"

    _patch_route_caches(monkeypatch, cache)
    patch_route_dependency(monkeypatch, advisor, "AsyncOpenAI", lambda **_kwargs: client)
    monkeypatch.setattr(advisor_scan_utils_module, "get_openai_client", lambda: client)
    monkeypatch.setattr(advisor_scan_utils_module, "build_story_context", _fake_story_context)
    cache_scopes: list[str] = []
    progress: list[tuple[int, int]] = []

    async def record_progress(completed: int, total: int) -> None:
        progress.append((completed, total))

    def record_scan_scope(scope, *_args):
        cache_scopes.append(scope)
        return scope

    monkeypatch.setattr(
        advisor_scan_utils_module,
        "make_editorial_cache_key",
        record_scan_scope,
    )
    monkeypatch.setattr(advisor.settings, "OPENAI_API_KEY", "test-key", raising=False)
    monkeypatch.setattr(advisor.settings, "OPENAI_INTEL_MODEL", "gpt-test", raising=False)

    user = SimpleNamespace(id=user_id)
    db = _FakeDB(
        get_values=[book, user],
        execute_values=[
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(all_rows=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(
                all_rows=[
                    (["River token", "Unmarked seal"], 8, "The Bargain"),
                    (["Missing map"], 9, "The Crossing"),
                ]
            ),
            _Result(
                all_rows=[
                    (
                        chapter,
                        f"Chapter {chapter}",
                        "The ferryman bargain remains unresolved after the crossing."
                        if chapter == 9
                        else "The gate was locked before the travelers arrived."
                        if chapter == 5
                        else f"A significant event occurs in chapter {chapter}.",
                        [{"event_title": f"Event {chapter}"}],
                    )
                    for chapter in range(9, 0, -1)
                ]
            ),
            _Result(scalar=0),
            _Result(scalar=0),
            _Result(scalar=0),
        ],
    )

    payload = await advisor_scan_utils_module.build_advisor_suggestions_payload(
        db=db,
        book=book,
        user_id=user_id,
        force_audit=True,
        on_audit_progress=record_progress,
    )

    assert progress == [(0, 3), (1, 3), (2, 3), (3, 3)]
    assert payload["meta"]["proactive_audit_applied"] is True
    assert cache_scopes and all(scope.startswith("scan:v4:") for scope in cache_scopes)
    assert any("River token" in call["messages"][1]["content"] for call in client.calls)
    assert any("Missing map" in call["messages"][1]["content"] for call in client.calls)
    assert payload["meta"]["fallback_applied"] is False
    if second_group_valid:
        assert "all 3 evidence groups" in payload["meta"]["audit_summary"]
        assert "2 distinct supported checks" in payload["meta"]["audit_summary"]
    else:
        assert "2 of 3 evidence groups" in payload["meta"]["audit_summary"]
        assert payload["meta"]["audit_failure_category"] == "invalid_ai_response"
    assert any(item["source"] == "proactive_audit" for item in payload["suggestions"])
    assert len(
        [item for item in payload["suggestions"] if item["source"] == "proactive_audit"]
    ) == (2 if second_group_valid else 1)
    assert payload["meta"]["audit_groups_total"] == 3
    assert payload["meta"]["audit_groups_completed"] == (3 if second_group_valid else 2)
    assert len(cache.set_calls) == (3 if second_group_valid else 2)
    assert client.closed is False


@pytest.mark.asyncio
async def test_large_advisor_scan_covers_all_thread_groups_with_bounded_parallelism(monkeypatch):
    book_id = uuid.uuid4()
    user_id = uuid.uuid4()
    book = SimpleNamespace(id=book_id, user_id=user_id, title="Atlas", total_chapters=3)
    threads = [
        SimpleNamespace(
            id=uuid.uuid4(),
            title=f"Thread {index:03d}",
            description=(
                "Earlier terms remain in force. " * 8 + "The final promise remains unresolved."
                if index == 164
                else f"Evidence for thread {index:03d}."
            ),
            status="introduced",
            importance=1,
            introduced_at=1,
            last_mentioned_at=1,
            resolved_at=None,
            mention_count=1,
        )
        for index in range(165)
    ]
    cache = _AsyncCache()
    progress: list[tuple[int, int]] = []
    seen_groups: list[str] = []
    seen_blocks: list[str] = []
    relationship = SimpleNamespace(
        id=uuid.uuid4(),
        character_a_id=uuid.uuid4(),
        character_b_id=uuid.uuid4(),
        rel_type="ally",
        from_chapter=2,
        description="They traveled together. " * 10 + "Their alliance ended at the gate.",
        sentiment=0.5,
        edited_by_author=True,
    )
    world_element = SimpleNamespace(
        id=uuid.uuid4(),
        name="Copper bridge",
        element_type="place",
        usage_count=2,
        gap_score=None,
        description="The crossing seemed stable. " * 10 + "The bridge was destroyed at dusk.",
    )
    active = 0
    peak_active = 0

    async def fake_story_context(*_args, **_kwargs):
        return "Story context"

    async def fake_scan(*, source_blocks, **_kwargs):
        nonlocal active, peak_active
        active += 1
        peak_active = max(peak_active, active)
        try:
            await asyncio.sleep(0)
            seen_blocks.extend(source_blocks)
            thread_blocks = [block for block in source_blocks if block.startswith("- Thread")]
            seen_groups.extend(thread_blocks)
            return {"findings": [], "overall_note": thread_blocks[-1]}
        finally:
            active -= 1

    async def record_progress(completed, total):
        progress.append((completed, total))

    _patch_route_caches(monkeypatch, cache)
    monkeypatch.setattr(advisor_scan_utils_module, "get_openai_client", lambda: object())
    monkeypatch.setattr(advisor_scan_utils_module, "build_story_context", fake_story_context)
    monkeypatch.setattr(advisor_scan_utils_module, "request_proactive_scan_result", fake_scan)
    monkeypatch.setattr(advisor.settings, "OPENAI_API_KEY", "test-key", raising=False)
    monkeypatch.setattr(advisor.settings, "OPENAI_INTEL_MODEL", "gpt-test", raising=False)
    monkeypatch.setattr(advisor.settings, "LLM_MAX_CONCURRENT_CALLS_PER_USER", 4, raising=False)
    db = _FakeDB(
        execute_values=[
            _Result(scalars=[]),
            _Result(scalars=threads),
            _Result(scalars=[relationship]),
            _Result(scalars=[world_element]),
            _Result(all_rows=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(all_rows=[]),
            _Result(all_rows=[]),
            _Result(scalar=0),
            _Result(scalar=0),
            _Result(scalar=0),
        ]
    )

    payload = await advisor_scan_utils_module.build_advisor_suggestions_payload(
        db=db,
        book=book,
        user_id=user_id,
        force_audit=True,
        on_audit_progress=record_progress,
    )

    assert peak_active == 2
    assert active == 0
    assert progress == [(index, 21) for index in range(22)]
    assert payload["meta"]["audit_groups_total"] == 21
    assert payload["meta"]["audit_groups_completed"] == 21
    assert payload["meta"]["audit_failure_category"] is None
    assert "all 21 evidence groups" in payload["meta"]["audit_summary"]
    assert "0 distinct supported checks" in payload["meta"]["audit_summary"]
    assert len(cache.set_calls) == 21
    assert {f"- Thread {index:03d}" for index in range(165)} <= {
        block.split(" [", 1)[0] for block in seen_groups
    }
    assert any("The final promise remains unresolved." in block for block in seen_groups)
    assert any("Their alliance ended at the gate." in block for block in seen_blocks)
    assert any("The bridge was destroyed at dusk." in block for block in seen_blocks)


@pytest.mark.asyncio
async def test_successful_empty_proactive_audit_returns_no_padded_findings(monkeypatch):
    book_id = uuid.uuid4()
    user_id = uuid.uuid4()
    book = SimpleNamespace(id=book_id, user_id=user_id, title="Atlas", total_chapters=2)
    cache = _AsyncCache()
    client = _FakeClient('{"findings":[],"overall_note":"No supported checks found."}')
    long_summary = (
        "The travelers waited by the old gate. " * 50
        + "The final key was lost after the gate closed."
    )
    key_events = [{"event_title": f"Event {number} changed the route"} for number in range(5)]

    async def _fake_story_context(*_args, **_kwargs):
        return "Story context"

    _patch_route_caches(monkeypatch, cache)
    monkeypatch.setattr(advisor_scan_utils_module, "get_openai_client", lambda: client)
    monkeypatch.setattr(advisor_scan_utils_module, "build_story_context", _fake_story_context)
    monkeypatch.setattr(advisor.settings, "OPENAI_API_KEY", "test-key", raising=False)
    monkeypatch.setattr(advisor.settings, "OPENAI_INTEL_MODEL", "gpt-test", raising=False)
    db = _FakeDB(
        execute_values=[
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(all_rows=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(all_rows=[([], 2, "Ending")]),
            _Result(all_rows=[(2, "Ending", long_summary, key_events)]),
        ],
    )

    payload = await advisor_scan_utils_module.build_advisor_suggestions_payload(
        db=db, book=book, user_id=user_id, force_audit=True
    )

    assert payload["suggestions"] == []
    assert payload["total"] == 0
    assert payload["meta"]["proactive_audit_applied"] is True
    assert payload["meta"]["fallback_applied"] is False
    assert payload["meta"]["audit_groups_total"] == 1
    assert payload["meta"]["audit_groups_completed"] == 1
    assert payload["meta"]["audit_failure_category"] is None
    assert len(cache.set_calls) == 1
    assert len(client.calls) == 1
    audit_prompt = client.calls[0]["messages"][1]["content"]
    assert "The final key was lost after the gate closed." in audit_prompt
    assert "Event 4 changed the route" in audit_prompt


@pytest.mark.asyncio
async def test_partial_proactive_audit_shows_verified_finding_without_caching_completion(
    monkeypatch,
):
    book_id = uuid.uuid4()
    user_id = uuid.uuid4()
    book = SimpleNamespace(id=book_id, user_id=user_id, title="Atlas", total_chapters=2)
    cache = _AsyncCache()

    async def _fake_story_context(*_args, **_kwargs):
        return "Story context"

    async def _partial_scan(**_kwargs):
        return {
            "findings": [
                {
                    "severity": "warning",
                    "type": "event_conflict",
                    "title": "Check gate timing",
                    "description": "The gate timing needs verification.",
                    "evidence_excerpt": "The gate closes.",
                    "chapter_ref": 2,
                    "action_label": "Trace the gate",
                    "ask_prompt": "When did the gate close?",
                }
            ],
            "overall_note": "Some checks lacked verifiable evidence and were omitted.",
            "partial": True,
        }

    _patch_route_caches(monkeypatch, cache)
    monkeypatch.setattr(advisor_scan_utils_module, "get_openai_client", lambda: _FakeClient())
    monkeypatch.setattr(advisor_scan_utils_module, "build_story_context", _fake_story_context)
    monkeypatch.setattr(advisor_scan_utils_module, "request_proactive_scan_result", _partial_scan)
    monkeypatch.setattr(advisor.settings, "OPENAI_API_KEY", "test-key", raising=False)
    monkeypatch.setattr(advisor.settings, "OPENAI_INTEL_MODEL", "gpt-test", raising=False)
    db = _FakeDB(
        execute_values=[
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(all_rows=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(all_rows=[([], 2, "Ending")]),
            _Result(all_rows=[(2, "Ending", "The gate closes.", [])]),
        ],
    )

    payload = await advisor_scan_utils_module.build_advisor_suggestions_payload(
        db=db, book=book, user_id=user_id, force_audit=True
    )

    assert [item["title"] for item in payload["suggestions"]] == ["Check gate timing"]
    assert payload["meta"]["proactive_audit_applied"] is True
    assert payload["meta"]["audit_groups_total"] == 1
    assert payload["meta"]["audit_groups_completed"] == 0
    assert payload["meta"]["audit_failure_category"] == "invalid_ai_response"
    assert not cache.set_calls


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("failure_kind", "expected_category"),
    [
        ("malformed", "invalid_ai_response"),
        ("provider_capacity", "ai_unavailable"),
        ("slot_contention", "capacity_busy"),
        ("monthly_budget", "budget_exhausted"),
    ],
)
async def test_failed_proactive_audit_is_not_cached_as_clean_scan(
    monkeypatch, failure_kind, expected_category
):
    book_id = uuid.uuid4()
    user_id = uuid.uuid4()
    book = SimpleNamespace(id=book_id, user_id=user_id, title="Atlas", total_chapters=2)
    cache = _AsyncCache()
    client = _FakeClient("not-json")

    async def _fake_story_context(*_args, **_kwargs):
        return "Story context"

    _patch_route_caches(monkeypatch, cache)
    monkeypatch.setattr(advisor_scan_utils_module, "get_openai_client", lambda: client)
    monkeypatch.setattr(advisor_scan_utils_module, "build_story_context", _fake_story_context)
    monkeypatch.setattr(
        advisor_scan_utils_module, "make_editorial_cache_key", lambda *_args: "scan-cache"
    )
    monkeypatch.setattr(advisor.settings, "OPENAI_API_KEY", "test-key", raising=False)
    monkeypatch.setattr(advisor.settings, "OPENAI_INTEL_MODEL", "gpt-test", raising=False)

    if failure_kind in {"provider_capacity", "slot_contention", "monthly_budget"}:

        async def unavailable_scan(**_kwargs):
            if failure_kind == "slot_contention":
                raise HTTPException(429, "LLM capacity is temporarily busy. Retry shortly.")
            if failure_kind == "monthly_budget":
                raise HTTPException(
                    429, {"kind": "llm_budget", "message": "Monthly AI capacity reached."}
                )
            raise HTTPException(503, "LLM provider capacity is temporarily unavailable.")

        monkeypatch.setattr(
            advisor_scan_utils_module, "request_proactive_scan_result", unavailable_scan
        )

    db = _FakeDB(
        get_values=[SimpleNamespace(id=user_id)],
        execute_values=[
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(all_rows=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(scalars=[]),
            _Result(all_rows=[([], 2, "Ending")]),
            _Result(all_rows=[(2, "Ending", "The gate closes.", [])]),
            _Result(scalar=0),
            _Result(scalar=0),
            _Result(scalar=0),
        ],
    )

    payload = await advisor_scan_utils_module.build_advisor_suggestions_payload(
        db=db, book=book, user_id=user_id, force_audit=True
    )

    assert payload["meta"]["audit_failure_category"] == expected_category
    assert "0 of 1 evidence groups" in payload["meta"]["audit_summary"]
    assert payload["meta"]["proactive_audit_applied"] is False
    assert not cache.set_calls


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

    cache = _AsyncCache(
        {
            (str(book_id), "editorial-key"): {
                "review": {"overall_verdict": "Cached"},
                "retrieved_passages": [],
            }
        }
    )
    patch_route_dependency(
        monkeypatch, advisor, "make_editorial_cache_key", lambda *_args: "editorial-key"
    )
    _patch_route_caches(monkeypatch, cache)
    db = _FakeDB(get_values=[book])
    cached_payload = await advisor.editorial_review(
        book_id,
        body=EditorialReviewRequest(text="Scene", chapter_num=2),
        db=db,
        current_user=SimpleNamespace(id=user_id),
        _=None,
    )
    assert cached_payload["cached"] is True

    cache = _AsyncCache()
    client = _FakeClient('{"overall_verdict":"Needs polish"}')
    search_calls: list[dict] = []

    async def _fake_semantic_search(*_args, **_kwargs):
        search_calls.append(dict(_kwargs))
        return [
            {
                "chapter_num": 2,
                "chapter_title": "Storm",
                "chunk_index": 7,
                "text": "Passage",
                "score": 0.81,
            }
        ]

    async def _fake_story_context(*_args, **_kwargs):
        return "Story context"

    _patch_route_caches(monkeypatch, cache)
    patch_route_dependency(
        monkeypatch, advisor, "make_editorial_cache_key", lambda *_args: "editorial-build"
    )
    patch_route_dependency(monkeypatch, advisor, "hybrid_story_search", _fake_semantic_search)
    patch_route_dependency(monkeypatch, advisor, "build_story_context", _fake_story_context)
    monkeypatch.setattr(
        advisor, "normalize_editorial_review_result", lambda raw: {"overall_verdict": raw}
    )
    patch_route_dependency(monkeypatch, advisor, "AsyncOpenAI", lambda **_kwargs: client)
    user = SimpleNamespace(id=user_id)
    db = _FakeDB(
        get_values=[book, user],
        execute_values=[_Result(scalar=0), _Result(scalar=0), _Result(scalar=0)],
    )

    payload = await advisor.editorial_review(
        book_id,
        body=EditorialReviewRequest(text="Scene", chapter_num=2),
        db=db,
        current_user=user,
        _=None,
    )

    assert payload["review"]["overall_verdict"] == '{"overall_verdict":"Needs polish"}'
    assert payload["retrieved_passages"][0]["chunk_index"] == 7
    assert search_calls[0]["limit"] == 8
    assert search_calls[0]["similarity_threshold"] == 0.28
    assert cache.set_calls
    assert client.closed is False


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
    patch_route_dependency(monkeypatch, advisor, "AsyncOpenAI", lambda **_kwargs: client)
    monkeypatch.setattr(
        advisor,
        "normalize_prose_tighten_result",
        lambda raw, _text: {"tightened_text": "Trimmed", "changed": True, "rationale": [raw]},
    )
    user = SimpleNamespace(id=user_id)
    db = _FakeDB(
        get_values=[book, user],
        execute_values=[_Result(scalar=0), _Result(scalar=0), _Result(scalar=0)],
    )

    payload = await advisor.prose_tighten(
        book_id,
        body=ProseTightenRequest(text="Long text", chapter_num=4),
        db=db,
        current_user=user,
        _=None,
    )

    assert payload.tightened_text == "Trimmed"
    assert payload.rationale[0].startswith("{")
    assert client.closed is False


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

    patch_route_dependency(monkeypatch, advisor, "editorial_review", _fake_editorial_review)
    patch_route_dependency(
        monkeypatch, advisor, "detect_chapter_continuity_flags", _fake_detect_flags
    )

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
    user = SimpleNamespace(id=user_id)
    db = _FakeDB(get_values=[book], execute_values=[_Result(all_rows=[])])

    with pytest.raises(HTTPException) as exc:
        await advisor.manuscript_synopsis(book_id, db=db, current_user=user)
    assert exc.value.detail == "No chapters available for synopsis generation."

    db = _FakeDB(
        get_values=[book, user],
        execute_values=[
            _Result(all_rows=[(1, "Start", "s3://one", 1), (2, None, None, 1)]),
            _Result(scalar=0),
            _Result(scalar=0),
            _Result(scalar=0),
        ],
    )
    client = _FakeClient('{"synopsis":"Short"}')
    patch_route_dependency(monkeypatch, advisor, "download_book", lambda _key: b"Chapter text")

    async def _fake_story_context(*_args, **_kwargs):
        return "Story context"

    patch_route_dependency(monkeypatch, advisor, "build_story_context", _fake_story_context)
    patch_route_dependency(monkeypatch, advisor, "AsyncOpenAI", lambda **_kwargs: client)
    monkeypatch.setattr(
        advisor,
        "normalize_synopsis_result",
        lambda raw, _spoiler: {"spoiler_level": "minimal", "synopsis": raw, "focus_points": []},
    )

    payload = await advisor.manuscript_synopsis(book_id, db=db, current_user=user)

    assert payload.synopsis.startswith("{")
    assert payload.coverage_chapters == [1, 2]
    assert payload.cached is False
    assert client.closed is False


@pytest.mark.asyncio
async def test_manuscript_synopsis_caching(monkeypatch):
    book_id = uuid.uuid4()
    user_id = uuid.uuid4()
    book = SimpleNamespace(id=book_id, user_id=user_id, title="Atlas", total_chapters=6)
    user = SimpleNamespace(id=user_id)

    db = _FakeDB(
        get_values=[book, user],
        execute_values=[
            _Result(all_rows=[(1, "Start", "s3://one", 1), (2, "Next", "s3://two", 1)]),
            _Result(scalar=0),
            _Result(scalar=0),
            _Result(scalar=0),
        ],
    )
    client = _FakeClient('{"synopsis":"A short synopsis."}', '{"synopsis":"Should not be called"}')
    patch_route_dependency(monkeypatch, advisor, "download_book", lambda _key: b"Chapter text")
    patch_route_dependency(monkeypatch, advisor, "AsyncOpenAI", lambda **_kwargs: client)

    async def _fake_story_context(*_args, **_kwargs):
        return "Story context"

    patch_route_dependency(monkeypatch, advisor, "build_story_context", _fake_story_context)
    monkeypatch.setattr(
        advisor,
        "normalize_synopsis_result",
        lambda raw, _spoiler: {
            "spoiler_level": "minimal",
            "synopsis": raw,
            "focus_points": ["premise"],
        },
    )

    stored_payload: dict | None = None

    async def _fake_set_synopsis_cache(bk_id, spoiler, ch, payload):
        nonlocal stored_payload
        stored_payload = payload

    patch_route_dependency(monkeypatch, advisor, "set_synopsis_cache", _fake_set_synopsis_cache)

    payload1 = await advisor.manuscript_synopsis(book_id, db=db, current_user=user)
    assert payload1.cached is False
    assert len(client.calls) == 1

    async def _fake_get_synopsis_cache(bk_id, spoiler, ch):
        if stored_payload is not None:
            return stored_payload
        return None

    patch_route_dependency(monkeypatch, advisor, "get_synopsis_cache", _fake_get_synopsis_cache)

    db2 = _FakeDB(
        get_values=[book],
        execute_values=[
            _Result(all_rows=[(1, "Start", "s3://one", 1), (2, "Next", "s3://two", 1)]),
        ],
    )
    payload2 = await advisor.manuscript_synopsis(
        book_id, db=db2, current_user=SimpleNamespace(id=user_id)
    )
    assert payload2.cached is True
    assert len(client.calls) == 1
    assert payload1.synopsis == payload2.synopsis


def _patch_fake_voice_cast_loader(monkeypatch) -> None:
    async def load_from_fake_db(db, *, book_id):
        return [dict(row) for row in (await db.execute(None)).mappings().all()]

    patch_route_dependency(monkeypatch, advisor, "load_voice_review_characters", load_from_fake_db)


@pytest.mark.asyncio
async def test_voice_consistency_review_does_not_score_without_verified_baseline(monkeypatch):
    _patch_fake_voice_cast_loader(monkeypatch)
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
    search_calls: list[dict] = []

    async def _fake_semantic_search(*_args, **_kwargs):
        search_calls.append(dict(_kwargs))
        return [
            {
                "chapter_num": 2,
                "chapter_title": "Storm",
                "chunk_index": 5,
                "text": "Excerpt",
                "score": 0.88,
            }
        ]

    async def _fake_story_context(*_args, **_kwargs):
        return "Story context"

    patch_route_dependency(monkeypatch, advisor, "semantic_search", _fake_semantic_search)
    patch_route_dependency(monkeypatch, advisor, "build_story_context", _fake_story_context)
    patch_route_dependency(
        monkeypatch,
        advisor,
        "identify_character_mentions",
        lambda _text, rows, **_kwargs: [rows[0]],
    )
    patch_route_dependency(
        monkeypatch, advisor, "extract_dialogue_samples_by_character", lambda *_args: {}
    )
    monkeypatch.setattr(
        advisor, "build_character_voice_context", lambda chars: f"chars:{len(chars)}"
    )
    patch_route_dependency(
        monkeypatch, advisor, "normalize_voice_consistency_result", lambda raw: {"review": raw}
    )
    monkeypatch.setattr(
        advisor, "compute_voice_metrics", lambda samples: {"sample_dialogue_count": len(samples)}
    )
    monkeypatch.setattr(
        advisor,
        "score_voice_match",
        lambda _profile, metrics: (0.87 if metrics["sample_dialogue_count"] else 0.52, ["cadence"]),
    )
    patch_route_dependency(monkeypatch, advisor, "AsyncOpenAI", lambda **_kwargs: client)

    user = SimpleNamespace(id=user_id)
    db = _FakeDB(
        get_values=[book, user],
        execute_values=[
            _Result(mappings=[{"id": char_id, "name": "Iris"}, {"id": other_id, "name": "Milo"}]),
            _Result(scalars=[profile, other_profile]),
            _Result(scalar=0),
            _Result(scalar=0),
            _Result(scalar=0),
        ],
    )

    passage = (
        "Iris says hello. " + "Quiet conversation followed. " * 180 + "Milo answered at the end."
    )
    payload = await advisor.voice_consistency_review(
        book_id,
        body=VoiceConsistencyRequest(text=passage, chapter_num=3),
        db=db,
        current_user=user,
        _=None,
    )

    assert payload["review"]["status"] == "insufficient_evidence"
    assert payload["characters_reviewed"] == []
    assert payload["character_matches"] == []
    assert not search_calls
    assert not client.calls
    assert client.closed is False


@pytest.mark.asyncio
async def test_voice_consistency_review_respects_selected_character(monkeypatch):
    _patch_fake_voice_cast_loader(monkeypatch)
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
            _Result(
                mappings=[
                    {"id": char_id, "name": "Iris"},
                    {"id": other_id, "name": "Milo"},
                ]
            ),
            _Result(scalars=[profile, other_profile]),
        ],
    )
    client = _FakeClient('{"overall_verdict":"steady","issues":[]}')

    async def _fake_semantic_search(*_args, **_kwargs):
        return []

    async def _fake_story_context(*_args, **_kwargs):
        return "Story context"

    patch_route_dependency(monkeypatch, advisor, "semantic_search", _fake_semantic_search)
    patch_route_dependency(monkeypatch, advisor, "build_story_context", _fake_story_context)
    patch_route_dependency(
        monkeypatch, advisor, "identify_character_mentions", lambda _text, rows: rows
    )
    monkeypatch.setattr(
        advisor, "extract_dialogue_samples_by_character", lambda *_args: {"Iris": ["Hello there."]}
    )
    monkeypatch.setattr(
        advisor, "build_character_voice_context", lambda chars: f"chars:{len(chars)}"
    )
    monkeypatch.setattr(
        advisor,
        "normalize_voice_consistency_result",
        lambda _raw: {"issues": [], "overall_verdict": "steady"},
    )
    monkeypatch.setattr(
        advisor, "compute_voice_metrics", lambda samples: {"sample_dialogue_count": len(samples)}
    )
    monkeypatch.setattr(
        advisor,
        "score_voice_match",
        lambda _profile, metrics: (87 if metrics["sample_dialogue_count"] else 52, ["cadence"]),
    )
    patch_route_dependency(monkeypatch, advisor, "AsyncOpenAI", lambda **_kwargs: client)

    user = SimpleNamespace(id=user_id)
    db = _FakeDB(
        get_values=[book, user],
        execute_values=[
            _Result(
                mappings=[
                    {"id": char_id, "name": "Iris"},
                    {"id": other_id, "name": "Milo"},
                ]
            ),
            _Result(scalars=[profile, other_profile]),
            _Result(scalar=0),
            _Result(scalar=0),
            _Result(scalar=0),
        ],
    )

    payload = await advisor.voice_consistency_review(
        book_id,
        body=VoiceConsistencyRequest(text="Iris says hello.", chapter_num=3, character_id=char_id),
        db=db,
        current_user=user,
        _=None,
    )

    assert payload["review"]["status"] == "insufficient_evidence"
    assert payload["character_matches"] == []
    assert any("Iris" in warning for warning in payload["warnings"])
    assert client.closed is False


@pytest.mark.asyncio
async def test_voice_consistency_review_rejects_character_from_another_book(monkeypatch):
    _patch_fake_voice_cast_loader(monkeypatch)
    book_id = uuid.uuid4()
    user_id = uuid.uuid4()
    selected_id = uuid.uuid4()
    other_id = uuid.uuid4()
    book = SimpleNamespace(id=book_id, user_id=user_id, title="Atlas", total_chapters=9)
    db = _FakeDB(
        get_values=[book],
        execute_values=[
            _Result(mappings=[{"id": other_id, "name": "Milo"}]),
        ],
    )

    async def _fake_semantic_search(*_args, **_kwargs):
        return []

    async def _fake_story_context(*_args, **_kwargs):
        return "Story context"

    patch_route_dependency(monkeypatch, advisor, "semantic_search", _fake_semantic_search)
    patch_route_dependency(monkeypatch, advisor, "build_story_context", _fake_story_context)

    with pytest.raises(HTTPException) as exc:
        await advisor.voice_consistency_review(
            book_id,
            body=VoiceConsistencyRequest(
                text="Iris says hello.", chapter_num=3, character_id=selected_id
            ),
            db=db,
            current_user=SimpleNamespace(id=user_id),
            _=None,
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "Selected character does not belong to this book."


@pytest.mark.asyncio
async def test_voice_consistency_review_does_not_treat_unattributed_prose_as_dialogue(
    monkeypatch,
):
    _patch_fake_voice_cast_loader(monkeypatch)
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
            _Result(
                mappings=[
                    {"id": char_id, "name": "Iris"},
                    {"id": other_id, "name": "Milo"},
                ]
            ),
            _Result(scalars=[profile, other_profile]),
        ],
    )
    client = _FakeClient('{"overall_verdict":"steady","issues":[]}')

    async def _fake_semantic_search(*_args, **_kwargs):
        return []

    async def _fake_story_context(*_args, **_kwargs):
        return "Story context"

    patch_route_dependency(monkeypatch, advisor, "semantic_search", _fake_semantic_search)
    patch_route_dependency(monkeypatch, advisor, "build_story_context", _fake_story_context)
    patch_route_dependency(
        monkeypatch, advisor, "extract_dialogue_samples_by_character", lambda *_args: {}
    )
    monkeypatch.setattr(
        advisor, "build_character_voice_context", lambda chars: f"chars:{len(chars)}"
    )
    monkeypatch.setattr(
        advisor,
        "normalize_voice_consistency_result",
        lambda _raw: {"issues": [], "overall_verdict": "steady"},
    )
    monkeypatch.setattr(
        advisor, "compute_voice_metrics", lambda samples: {"sample_dialogue_count": len(samples)}
    )
    monkeypatch.setattr(
        advisor,
        "score_voice_match",
        lambda _profile, metrics: (71 if metrics["sample_dialogue_count"] else 52, ["cadence"]),
    )
    patch_route_dependency(monkeypatch, advisor, "AsyncOpenAI", lambda **_kwargs: client)

    user = SimpleNamespace(id=user_id)
    db = _FakeDB(
        get_values=[book, user],
        execute_values=[
            _Result(
                mappings=[
                    {"id": char_id, "name": "Iris"},
                    {"id": other_id, "name": "Milo"},
                ]
            ),
            _Result(scalars=[profile, other_profile]),
            _Result(scalar=0),
            _Result(scalar=0),
            _Result(scalar=0),
        ],
    )

    payload = await advisor.voice_consistency_review(
        book_id,
        body=VoiceConsistencyRequest(text="Iris says hello.", chapter_num=3, character_id=char_id),
        db=db,
        current_user=user,
        _=None,
    )

    assert payload["review"]["status"] == "insufficient_evidence"
    assert payload["characters_reviewed"] == []
    assert payload["character_matches"] == []
    assert not client.calls
    assert client.closed is False


@pytest.mark.asyncio
@pytest.mark.parametrize("baseline_contextual", [False, True])
async def test_voice_consistency_review_uses_verified_external_baseline_and_caches_complete_result(
    monkeypatch,
    baseline_contextual,
):
    _patch_fake_voice_cast_loader(monkeypatch)
    book_id = uuid.uuid4()
    user_id = uuid.uuid4()
    char_id = uuid.uuid4()
    book = SimpleNamespace(id=book_id, user_id=user_id, title="Atlas", total_chapters=3)
    user = SimpleNamespace(id=user_id)
    db = _FakeDB(
        get_values=[book, user],
        execute_values=[_Result(mappings=[{"id": char_id, "name": "Iris", "aliases": []}])],
    )
    baseline = [
        {
            "chapter_number": 1,
            "excerpt": f"I shall explain the matter carefully in the morning before we meet again at the old house beyond the quiet river every evening number {index}.",
            **({"attribution_confidence": "contextual"} if baseline_contextual else {}),
        }
        for index in range(3)
    ]
    client = _FakeClient(
        '{"issues":[],"overall_verdict":"No supported voice shift in this section."}'
    )
    cache = _AsyncCache()

    async def fake_baseline(*_args, **_kwargs):
        return baseline

    async def fake_context(*_args, **_kwargs):
        return "Stored story context"

    _patch_route_caches(monkeypatch, cache)
    patch_route_dependency(monkeypatch, advisor, "load_voice_baseline_samples", fake_baseline)
    patch_route_dependency(monkeypatch, advisor, "build_story_context", fake_context)
    patch_route_dependency(monkeypatch, advisor, "AsyncOpenAI", lambda **_kwargs: client)

    submitted = (
        'Iris said, "I shall explain this matter tomorrow after the council meets by the river." '
        'Iris replied, "We should wait until every traveler has returned before deciding what happens next."'
    )
    payload = await advisor.voice_consistency_review(
        book_id,
        body=VoiceConsistencyRequest(
            text=submitted,
            chapter_num=2,
            character_id=char_id,
        ),
        db=db,
        current_user=user,
        _=None,
    )

    assert payload["review"]["status"] == (
        "partial_evidence" if baseline_contextual else "complete"
    )
    assert payload["characters_reviewed"] == ["Iris"]
    assert payload["coverage"]["total_characters"] == len(submitted)
    assert payload["baseline_evidence"][0]["baseline_attribution_confidence"] == (
        "contextual" if baseline_contextual else "explicit"
    )
    if baseline_contextual:
        assert payload["character_matches"] == []
        assert any("no numeric voice match" in warning for warning in payload["warnings"])
    else:
        assert payload["character_matches"][0]["baseline_sample_size"] == 3
    assert db.commits == 1
    assert len(client.calls) == 1
    assert bool(cache.set_calls) is not baseline_contextual


@pytest.mark.asyncio
async def test_first_person_voice_review_does_not_guess_unnamed_narrator(monkeypatch):
    _patch_fake_voice_cast_loader(monkeypatch)
    book_id = uuid.uuid4()
    user_id = uuid.uuid4()
    book = SimpleNamespace(id=book_id, user_id=user_id, title="Atlas", total_chapters=3)
    user = SimpleNamespace(id=user_id)
    db = _FakeDB(
        get_values=[book, user],
        execute_values=[_Result(mappings=[{"id": uuid.uuid4(), "name": "Iris", "aliases": []}])],
    )

    async def fake_story_context(*_args, **_kwargs):
        return "Story context"

    patch_route_dependency(monkeypatch, advisor, "build_story_context", fake_story_context)
    payload = await advisor.voice_consistency_review(
        book_id,
        body=VoiceConsistencyRequest(text="I walked home.", voice_mode="first_person_narration"),
        db=db,
        current_user=user,
        _=None,
    )

    assert payload["review"]["status"] == "insufficient_evidence"
    assert payload["characters_detected"] == []
    assert "no identity was guessed" in " ".join(payload["warnings"]).lower()


@pytest.mark.asyncio
async def test_first_person_voice_review_explains_missing_narration_baseline(monkeypatch):
    _patch_fake_voice_cast_loader(monkeypatch)
    book_id = uuid.uuid4()
    user_id = uuid.uuid4()
    narrator_id = uuid.uuid4()
    book = SimpleNamespace(id=book_id, user_id=user_id, title="Atlas", total_chapters=3)
    user = SimpleNamespace(id=user_id)
    db = _FakeDB(
        get_values=[book, user],
        execute_values=[_Result(mappings=[{"id": narrator_id, "name": "Iris", "aliases": []}])],
    )

    async def fake_story_context(*_args, **_kwargs):
        return "Story context"

    async def fake_baseline(*_args, **_kwargs):
        return []

    patch_route_dependency(monkeypatch, advisor, "build_story_context", fake_story_context)
    patch_route_dependency(monkeypatch, advisor, "load_voice_baseline_samples", fake_baseline)

    payload = await advisor.voice_consistency_review(
        book_id,
        body=VoiceConsistencyRequest(
            text="I crossed the square and watched the last train leave before dawn.",
            chapter_num=2,
            character_id=narrator_id,
            voice_mode="first_person_narration",
        ),
        db=db,
        current_user=user,
        _=None,
    )

    assert payload["review"]["status"] == "insufficient_evidence"
    assert "established first-person narration" in payload["review"]["overall_verdict"]
    assert "dialogue" not in payload["review"]["overall_verdict"]


def test_make_editorial_cache_key_varies_with_character_selection():
    book_id = uuid.uuid4()
    text = "Same passage"

    auto_key = advisor.make_editorial_cache_key(book_id, text, 4)
    selected_key = advisor.make_editorial_cache_key(book_id, text, 4, uuid.uuid4())

    assert auto_key != selected_key


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

    patch_route_dependency(monkeypatch, advisor, "editorial_review", _fake_editorial_review)
    patch_route_dependency(monkeypatch, advisor, "advisor_suggestions", _fake_suggestions)
    patch_route_dependency(
        monkeypatch, advisor, "build_continuity_report_markdown", lambda **_kwargs: "# Report"
    )
    monkeypatch.setattr(
        advisor, "build_continuity_report_pdf", lambda markdown, **_kwargs: markdown.encode("utf-8")
    )

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
async def test_series_advisor_message_enqueues_task(monkeypatch):
    series_id = uuid.uuid4()
    user_id = uuid.uuid4()
    series = SimpleNamespace(id=series_id, user_id=user_id, name="Atlas Saga")
    cache = _AsyncCache()
    db = _FakeDB(get_values=[series])
    captured: dict[str, object] = {}
    job_id = uuid.uuid4()

    class _Task:
        def apply_async(self, *, task_id, kwargs):
            captured["task_id"] = task_id
            captured["kwargs"] = kwargs

    async def _fake_create_job(*_args, **_kwargs):
        return SimpleNamespace(id=job_id)

    _patch_route_caches(monkeypatch, cache)
    patch_route_dependency(
        monkeypatch, advisor, "make_advisor_cache_key", lambda *_args: "series-key"
    )
    patch_route_dependency(monkeypatch, advisor, "generate_series_advisor_reply_task", _Task())
    patch_route_dependency(monkeypatch, advisor, "create_advisor_job", _fake_create_job)

    response = Response()
    payload = await advisor.series_advisor_message(
        series_id,
        body=_message_body(("assistant", "ctx"), ("user", "Anything?")),
        response=response,
        db=db,
        current_user=SimpleNamespace(id=user_id),
        _=None,
    )

    assert response.status_code == 202
    assert payload == {"task_id": str(job_id), "status": "queued", "cached": False}
    assert captured["task_id"] == str(job_id)
    assert captured["kwargs"] == {
        "job_id": str(job_id),
        "series_id": str(series_id),
        "user_id": str(user_id),
        "messages": [
            {"role": "assistant", "content": "ctx"},
            {"role": "user", "content": "Anything?"},
        ],
    }


@pytest.mark.asyncio
async def test_series_advisor_message_marks_job_failed_when_enqueue_fails(monkeypatch):
    series_id = uuid.uuid4()
    user_id = uuid.uuid4()
    series = SimpleNamespace(id=series_id, user_id=user_id, name="Atlas Saga")
    cache = _AsyncCache()
    db = _FakeDB(get_values=[series])
    job_id = uuid.uuid4()
    failed: dict[str, object] = {}

    class _Task:
        def apply_async(self, *, task_id, kwargs):
            raise RuntimeError("series broker unavailable")

    async def _fake_create_job(*_args, **_kwargs):
        return SimpleNamespace(id=job_id)

    async def _fake_mark_failed(*_args, **kwargs):
        failed.update(kwargs)

    _patch_route_caches(monkeypatch, cache)
    patch_route_dependency(
        monkeypatch, advisor, "make_advisor_cache_key", lambda *_args: "series-key"
    )
    patch_route_dependency(monkeypatch, advisor, "generate_series_advisor_reply_task", _Task())
    patch_route_dependency(monkeypatch, advisor, "create_advisor_job", _fake_create_job)
    patch_route_dependency(monkeypatch, advisor, "mark_advisor_job_failed", _fake_mark_failed)

    with pytest.raises(RuntimeError, match="series broker unavailable"):
        await advisor.series_advisor_message(
            series_id,
            body=_message_body(("assistant", "ctx"), ("user", "Anything?")),
            response=Response(),
            db=db,
            current_user=SimpleNamespace(id=user_id),
            _=None,
        )

    assert failed["job_id"] == job_id
    assert failed["error_code"] == "advisor_enqueue_failed"


@pytest.mark.asyncio
async def test_series_advisor_message_status_returns_completed_payload(monkeypatch):
    series_id = uuid.uuid4()
    user_id = uuid.uuid4()
    series = SimpleNamespace(id=series_id, user_id=user_id, name="Atlas Saga")
    job_id = uuid.uuid4()
    job = SimpleNamespace(
        id=job_id,
        user_id=user_id,
        scope="series",
        series_id=series_id,
        status="complete",
        result_json={
            "reply": "Series reply",
            "intent": "direction",
            "response_type": "standard",
            "retrieved_passages": [],
        },
        error_code=None,
    )
    db = _FakeDB(get_values=[series, job])

    payload = await advisor.series_advisor_message_status(
        series_id,
        str(job_id),
        db=db,
        current_user=SimpleNamespace(id=user_id),
    )

    assert payload["status"] == "complete"
    assert payload["result"]["reply"] == "Series reply"


@pytest.mark.asyncio
async def test_series_continuity_check_handles_no_prior_books_and_full_review(monkeypatch):
    series_id = uuid.uuid4()
    book_id = uuid.uuid4()
    prior_id = uuid.uuid4()
    user_id = uuid.uuid4()
    series = SimpleNamespace(id=series_id, user_id=user_id, name="Atlas Saga")
    current_book = SimpleNamespace(id=book_id, user_id=user_id, title="Book Two")
    cache = _AsyncCache()
    _patch_route_caches(monkeypatch, cache)
    patch_route_dependency(
        monkeypatch, advisor, "make_editorial_cache_key", lambda *_args: "series-cont-key"
    )

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

    async def _fake_series_hits(*_args, **_kwargs):
        return [
            {
                "text": "Earlier clue",
                "chapter_num": 4,
                "chapter_title": "Vault",
                "book_title": "Book One",
                "relevance": 0.8,
            }
        ]

    patch_route_dependency(monkeypatch, advisor, "build_series_story_context", _fake_story_context)
    patch_route_dependency(
        monkeypatch, advisor, "retrieve_series_continuity_passages", _fake_series_hits
    )
    monkeypatch.setattr(
        advisor, "normalize_series_continuity_result", lambda raw: {"overall_verdict": raw}
    )
    patch_route_dependency(monkeypatch, advisor, "AsyncOpenAI", lambda **_kwargs: client)
    user = SimpleNamespace(id=user_id)
    db = _FakeDB(
        get_values=[series, current_book, user],
        execute_values=[
            _Result(
                all_rows=[
                    SimpleNamespace(book_id=prior_id, position=1),
                    SimpleNamespace(book_id=book_id, position=2),
                ]
            ),
            _Result(all_rows=[SimpleNamespace(id=prior_id, title="Book One")]),
            _Result(scalar=0),
            _Result(scalar=0),
            _Result(scalar=0),
        ],
    )

    payload = await advisor.series_continuity_check(
        series_id,
        body=body,
        db=db,
        current_user=user,
        _=None,
    )

    assert payload["review"]["overall_verdict"].startswith("{")
    assert payload["retrieved_passages"][0]["book_title"] == "Book One"
    assert cache.set_calls
    assert client.closed is False
