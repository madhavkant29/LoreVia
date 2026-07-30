import uuid
from types import SimpleNamespace

import pytest
from httpx import Request
from openai import APIConnectionError

from app.services import extraction_chapter_llm_service
from app.services.extraction_chapter_llm_service import collect_chapter_llm_extraction


@pytest.mark.asyncio
async def test_collect_chapter_llm_extraction_normalizes_entities_and_relationships(monkeypatch):
    book_id = uuid.uuid4()
    user_id = uuid.uuid4()
    book = SimpleNamespace(id=book_id, user_id=user_id, language="en")
    known_character = SimpleNamespace(name="Known", aliases=[])
    calls = []

    monkeypatch.setattr(
        extraction_chapter_llm_service,
        "_group_chunks_for_extraction",
        lambda chunks: [["chunk one"], ["chunk two", "chunk three"]],
    )
    monkeypatch.setattr(
        extraction_chapter_llm_service,
        "build_character_roster_snapshot",
        lambda characters: [{"name": char.name} for char in characters],
    )

    async def fake_extract(batch_text, *, user_id, book_id, known_characters, usage_db, language):
        assert usage_db is None
        calls.append((batch_text, user_id, book_id, known_characters, usage_db, language))
        return {
            "characters": [
                {"name": "Ada", "confidence": 0.91},
                {"name": ""},
                "not-a-character",
            ],
            "relationships": [
                {"character_a": "Ada", "character_b": "Known", "rel_type": "ally"},
                {"character_a": "Ada"},
                "not-a-relationship",
            ],
            "rejected_characters": [{"name": "The City", "reason": "place"}],
        }

    monkeypatch.setattr(
        extraction_chapter_llm_service,
        "extract_characters_and_relationships",
        fake_extract,
    )

    result = await collect_chapter_llm_extraction(
        object(),
        book=book,
        chapter_number=7,
        chunks=["chunk one", "chunk two", "chunk three"],
        existing_characters=[known_character],
    )

    assert result.extraction_batch_texts == ["chunk one", "chunk two\n\nchunk three"]
    assert result.batch_count == 2
    assert result.extraction_failed_batches == 0
    assert result.extraction_fallback_batches == 0
    assert [entity["name"] for entity in result.raw_character_entities] == ["Ada", "Ada"]
    assert result.raw_character_entities[0]["_source_batch_key"] == f"{book_id}:7:1"
    assert result.raw_character_entities[1]["_source_text"] == "chunk two\n\nchunk three"
    assert result.pending_relationships == [
        {
            "character_a": "Ada",
            "character_b": "Known",
            "rel_type": "ally",
            "source_batch_key": f"{book_id}:7:1",
        },
        {
            "character_a": "Ada",
            "character_b": "Known",
            "rel_type": "ally",
            "source_batch_key": f"{book_id}:7:2",
        },
    ]
    assert result.extraction_rejected_characters == [
        {
            "name": "The City",
            "stage": "",
            "reason": "place",
            "confidence": None,
            "evidence": {},
        }
    ]
    assert calls[0][3] == [{"name": "Known"}]


@pytest.mark.asyncio
async def test_collect_chapter_llm_extraction_falls_back_after_batch_failure(monkeypatch):
    book = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4(), language="en")

    monkeypatch.setattr(
        extraction_chapter_llm_service,
        "_group_chunks_for_extraction",
        lambda chunks: [["chunk one"]],
    )
    monkeypatch.setattr(
        extraction_chapter_llm_service,
        "build_character_roster_snapshot",
        lambda characters: [],
    )

    async def fake_extract(*args, **kwargs):
        raise RuntimeError("primary extractor failed")

    async def fake_fallback(batch_text, *, user_id, book_id, usage_db, language):
        return {
            "characters": [{"name": "Fallback Ada"}],
            "relationships": [],
            "rejected_characters": [],
        }

    monkeypatch.setattr(
        extraction_chapter_llm_service,
        "extract_characters_and_relationships",
        fake_extract,
    )
    monkeypatch.setattr(
        extraction_chapter_llm_service,
        "fallback_character_mentions",
        fake_fallback,
    )

    result = await collect_chapter_llm_extraction(
        object(),
        book=book,
        chapter_number=2,
        chunks=["chunk one"],
        existing_characters=[],
    )

    assert result.extraction_failed_batches == 1
    assert result.extraction_fallback_batches == 1
    assert result.extraction_fallback_character_count == 1
    assert [entity["name"] for entity in result.raw_character_entities] == ["Fallback Ada"]


@pytest.mark.asyncio
async def test_collect_chapter_llm_extraction_does_not_fallback_on_provider_failure(monkeypatch):
    book = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4(), language="en")
    fallback_calls = 0

    monkeypatch.setattr(
        extraction_chapter_llm_service,
        "_group_chunks_for_extraction",
        lambda chunks: [["chunk one"]],
    )
    monkeypatch.setattr(
        extraction_chapter_llm_service,
        "build_character_roster_snapshot",
        lambda characters: [],
    )

    async def fake_extract(*_args, **_kwargs):
        raise APIConnectionError(
            request=Request("POST", "https://api.openai.com/v1/chat/completions")
        )

    async def fake_fallback(*_args, **_kwargs):
        nonlocal fallback_calls
        fallback_calls += 1
        return {"characters": [], "relationships": []}

    monkeypatch.setattr(
        extraction_chapter_llm_service,
        "extract_characters_and_relationships",
        fake_extract,
    )
    monkeypatch.setattr(
        extraction_chapter_llm_service,
        "fallback_character_mentions",
        fake_fallback,
    )

    with pytest.raises(APIConnectionError):
        await collect_chapter_llm_extraction(
            object(),
            book=book,
            chapter_number=2,
            chunks=["chunk one"],
            existing_characters=[],
        )

    assert fallback_calls == 0
