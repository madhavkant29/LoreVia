import json
import uuid
from types import SimpleNamespace

import pytest
from httpx import Request
from openai import APIConnectionError

from app.engine.character import extractor
from app.engine.character.extractor import CharacterExtractionFormatError
from app.services import extraction_chapter_llm_service, extraction_character_profile_service
from app.services.extraction_chapter_llm_service import collect_chapter_llm_extraction
from app.services.extraction_character_decision_service import _can_auto_save_character
from app.utils.characters.candidates import (
    decide_character_candidate_disposition,
    recurring_role_review_supported,
)


@pytest.mark.asyncio
@pytest.mark.parametrize("chunks", [[], [""], ["  \n "]])
async def test_collect_chapter_llm_extraction_marks_empty_source_incomplete_without_ai_call(
    monkeypatch, chunks
):
    book = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4(), language="en")
    recorded = []

    async def unexpected_extract(*_args, **_kwargs):
        raise AssertionError("Missing source text must not trigger an AI call")

    async def record_incomplete(coverage):
        recorded.append(dict(coverage))

    monkeypatch.setattr(
        extraction_chapter_llm_service,
        "extract_characters_and_relationships",
        unexpected_extract,
    )
    with pytest.raises(ValueError, match="character_extraction_empty_source"):
        await collect_chapter_llm_extraction(
            object(),
            book=book,
            chapter_number=1,
            chunks=chunks,
            existing_characters=[],
            on_incomplete_batch=record_incomplete,
        )

    assert recorded[0]["complete"] is False
    assert recorded[0]["failure_stage"] == "character_source_empty"
    assert recorded[0]["batch_outcomes"] == []


@pytest.mark.asyncio
async def test_recurring_unnamed_person_keeps_source_verified_review_evidence(monkeypatch):
    source = (
        "The guard opened the gate. Later the guard checked my pass. "
        'The guard said, "Wait here." I thanked the guard.'
    )
    book = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4(), language="en")

    async def fake_extract(batch_text, **_kwargs):
        strict_hints, _review_hints = extractor.collect_character_discovery_hints(batch_text)
        entities = extractor._clean_character_entries(
            [
                {
                    "name": "the guard",
                    "entity_type": "person",
                    "is_character": True,
                    "confidence": 0.95,
                }
            ],
            strict_hints,
            batch_text,
        )
        assert len(entities) == 1
        entities[0]["evidence"]["verifier"] = {
            "final": {"confidence_band": "accept", "is_person_like": True, "reasons": []},
            "llm": {"is_person_like": True},
        }
        return {"characters": entities, "relationships": []}

    async def retain_entities(entities, **_kwargs):
        return entities

    monkeypatch.setattr(
        extraction_chapter_llm_service, "extract_characters_and_relationships", fake_extract
    )
    monkeypatch.setattr(
        extraction_chapter_llm_service, "enrich_chapter_character_profiles", retain_entities
    )
    result = await collect_chapter_llm_extraction(
        object(),
        book=book,
        chapter_number=1,
        chunks=[source],
        existing_characters=[],
    )

    entity = result.aggregated_character_entities[0]
    evidence = entity["evidence"]
    assert entity["name"] == "the guard"
    assert evidence["mention_count"] == 4
    assert evidence["source_mention_count_verified"] is True
    assert recurring_role_review_supported(entity["name"], evidence) is True
    assert (
        decide_character_candidate_disposition(
            name=entity["name"], evidence=evidence, confidence=entity["confidence"]
        ).status
        == "pending"
    )


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

    async def fake_extract(
        batch_text,
        *,
        user_id,
        book_id,
        known_characters,
        usage_db,
        language,
        discovery_only,
    ):
        assert usage_db is None
        assert discovery_only is True
        calls.append((batch_text, user_id, book_id, known_characters, usage_db, language))
        return {
            "characters": [
                {"name": "Ada", "confidence": 0.91},
                {"name": ""},
                "not-a-character",
            ],
            "relationships": [
                {
                    "character_a": "Ada",
                    "character_b": "Known",
                    "rel_type": "ally",
                    "label_evidence": {"quote": batch_text, "confidence": 0.8},
                },
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

    async def fake_enrich(entities, **_kwargs):
        return entities

    monkeypatch.setattr(
        extraction_chapter_llm_service,
        "enrich_chapter_character_profiles",
        fake_enrich,
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
    assert result.source_coverage["complete"] is True
    assert result.source_coverage["batch_outcomes"] == [
        {"batch_index": 1, "status": "succeeded"},
        {"batch_index": 2, "status": "succeeded"},
    ]
    assert result.source_coverage["profile_enrichment"] == {
        "status": "complete",
        "identity_clusters": 1,
        "evidence_passages": 0,
        "unanchored_references": 0,
    }
    assert len(result.source_coverage["ranges"]) == 3
    assert result.extraction_failed_batches == 0
    assert result.extraction_fallback_batches == 0
    assert [entity["name"] for entity in result.raw_character_entities] == ["Ada", "Ada"]
    assert result.raw_character_entities[0]["_source_batch_key"] == f"{book_id}:7:1"
    assert result.raw_character_entities[0]["_source_start"] is None
    assert len(result.aggregated_character_entities) == 1
    assert result.raw_character_entities[1]["_source_text"] == ""
    assert result.raw_character_entities[1]["_source_windows"] == []
    assert result.pending_relationships == [
        {
            "character_a": "Ada",
            "character_b": "Known",
            "rel_type": "ally",
            "label_evidence": {
                "quote": "chunk one",
                "confidence": 0.8,
                "source_start": 0,
                "source_end": 9,
            },
            "source_quote_verified": True,
            "source_batch_key": f"{book_id}:7:1",
        },
        {
            "character_a": "Ada",
            "character_b": "Known",
            "rel_type": "ally",
            "label_evidence": {
                "quote": "chunk two\n\nchunk three",
                "confidence": 0.8,
                "source_start": 0,
                "source_end": 22,
            },
            "source_quote_verified": True,
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
@pytest.mark.parametrize(
    ("chunks", "existing_characters"),
    [
        (
            [
                "Madame Quill checked the ledger.",
                "I followed Quill. Quill warned the porter. Quill texted me later.",
                "Monsieur Quill called from the station.",
            ],
            [],
        ),
        (
            [
                "I followed Quill. Quill warned the porter. Quill texted me later.",
                "Monsieur Quill called from the station.",
            ],
            [SimpleNamespace(name="Madame Quill", aliases=[])],
        ),
        (
            [
                "I followed Quill. Quill warned the porter. Quill texted me later.",
                "Monsieur Quill called from the station.",
            ],
            [SimpleNamespace(name="Aunt Lena", aliases=["Madame Quill"])],
        ),
    ],
)
async def test_separate_batches_or_roster_hold_shared_surname_candidate_from_auto_save(
    monkeypatch, chunks, existing_characters
):
    book = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4(), language="en")
    monkeypatch.setattr(
        extraction_chapter_llm_service,
        "_group_chunks_for_extraction",
        lambda source_chunks: [[chunk] for chunk in source_chunks],
    )
    monkeypatch.setattr(
        extraction_chapter_llm_service,
        "build_character_roster_snapshot",
        lambda characters: [
            {"name": character.name, "aliases": character.aliases} for character in characters
        ],
    )

    async def fake_extract(batch_text, **_kwargs):
        if "I followed Quill" not in batch_text:
            return {"characters": [], "relationships": []}
        return {
            "characters": [
                {
                    "name": "Quill",
                    "confidence": 0.95,
                    "evidence": {
                        "mention_count": 3,
                        "strong_mention_count": 3,
                        "has_dialogue_or_action": True,
                        "has_direct_communication": True,
                        "verifier": {
                            "local": {
                                "person_context_mentions": 3,
                                "mid_sentence_mentions": 2,
                                "non_person_ner_mentions": 0,
                            },
                            "final": {"confidence_band": "accept", "is_person_like": True},
                        },
                    },
                }
            ],
            "relationships": [],
        }

    async def fake_enrich(entities, **_kwargs):
        return entities

    monkeypatch.setattr(
        extraction_chapter_llm_service, "extract_characters_and_relationships", fake_extract
    )
    monkeypatch.setattr(
        extraction_chapter_llm_service, "enrich_chapter_character_profiles", fake_enrich
    )

    result = await collect_chapter_llm_extraction(
        object(),
        book=book,
        chapter_number=1,
        chunks=chunks,
        existing_characters=existing_characters,
    )

    entity = result.aggregated_character_entities[0]
    assert entity["evidence"]["ambiguous_full_name_fragment"] is True
    assert _can_auto_save_character(entity) is False


def test_candidate_source_excerpt_keeps_late_mention_and_handles_missing_name():
    from app.utils.characters.text import (
        source_excerpt_around_name,
        source_excerpt_range_around_name,
        source_excerpt_ranges_around_names,
    )

    source = "x" * 3_000 + " Ada stepped forward."
    excerpt = source_excerpt_around_name(source, "Ada")

    assert len(excerpt) <= 2_200
    assert "Ada stepped forward." in excerpt
    start, end = source_excerpt_range_around_name(source, "Ada")
    assert source[start:end] == excerpt
    assert start > 0
    assert source_excerpt_around_name(source, "Missing") == source[:2_200]
    assert source_excerpt_around_name("short", "Ada") == "short"
    with pytest.raises(ValueError, match="invalid_source_excerpt_size"):
        source_excerpt_range_around_name(source, "Ada", max_chars=0)
    late_source = "Ada arrived. " + "x" * 3_000 + " Ada feared the storm."
    windows = source_excerpt_ranges_around_names(late_source, ["Ada"], max_chars=600)
    assert len(windows) == 2
    assert all(end - start <= 600 for start, end in windows)
    assert "Ada arrived." in late_source[slice(*windows[0])]
    assert "Ada feared the storm." in late_source[slice(*windows[1])]
    assert source_excerpt_ranges_around_names("Adaline arrived.", ["Ada"]) == []
    assert source_excerpt_ranges_around_names("", ["Ada"]) == []
    misleading_prefix = "Adaline crossed the square. " + "x" * 3_000 + " Ada found the key."
    start, end = source_excerpt_range_around_name(misleading_prefix, "Ada", max_chars=600)
    assert start > 0
    assert "Ada found the key." in misleading_prefix[start:end]
    assert "Adaline crossed the square." not in misleading_prefix[start:end]
    alias_source = "x" * 3_000 + " Mara Vale's sister arrived."
    start, end = source_excerpt_range_around_name(
        alias_source, ["Mara Ellison", "Mara Vale"], max_chars=600
    )
    assert start > 0
    assert "Mara Vale's sister arrived." in alias_source[start:end]
    assert source_excerpt_range_around_name(source, ["Absent", "Missing"]) == (0, 2_200)
    with pytest.raises(ValueError, match="invalid_source_excerpt_size"):
        source_excerpt_ranges_around_names(source, ["Ada"], max_chars=0)


@pytest.mark.asyncio
async def test_collect_chapter_llm_extraction_anchors_alias_when_canonical_name_is_absent(
    monkeypatch,
):
    book = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4(), language="en")
    source = "x" * 3_000 + " Mara opened the gate."

    async def fake_extract(_batch_text, **_kwargs):
        return {
            "characters": [{"name": "Mara Ellison", "aliases": ["Mara"]}],
            "relationships": [],
            "rejected_characters": [],
        }

    async def fake_enrich(entities, **_kwargs):
        return entities

    monkeypatch.setattr(
        extraction_chapter_llm_service, "extract_characters_and_relationships", fake_extract
    )
    monkeypatch.setattr(
        extraction_chapter_llm_service, "enrich_chapter_character_profiles", fake_enrich
    )

    result = await collect_chapter_llm_extraction(
        object(), book=book, chapter_number=1, chunks=[source], existing_characters=[]
    )

    entity = result.raw_character_entities[0]
    assert entity["_source_start"] > 0
    assert "Mara opened the gate." in entity["_source_text"]
    assert entity["_source_windows"]
    assert entity["_source_mentions"] == [
        {"chunk_index": 0, "start": source.index("Mara"), "end": source.index("Mara") + 4}
    ]


def test_candidate_source_excerpt_uses_original_unicode_offsets():
    from app.utils.characters.text import source_excerpt_range_around_name

    source = "İ" * 1_500 + " Mara " + "x" * 3_000
    start, end = source_excerpt_range_around_name(source, "mara", max_chars=600)

    assert start <= source.index("Mara") < end
    assert "Mara" in source[start:end]


def test_profile_windows_include_action_after_mention_near_previous_window_edge():
    from app.utils.characters.text import source_excerpt_ranges_around_names

    source = "Ada arrived. " + "x" * 500 + " Ada " + "y" * 160 + " unlocked the gate."

    windows = source_excerpt_ranges_around_names(source, ["Ada"], max_chars=600)

    assert len(windows) == 2
    assert all(end - start <= 600 for start, end in windows)
    assert "unlocked the gate." not in source[slice(*windows[0])]
    assert "Ada " in source[slice(*windows[1])]
    assert "unlocked the gate." in source[slice(*windows[1])]
    assert source_excerpt_ranges_around_names(
        "Ada met Mara. " + "x" * 700, ["Ada", "Mara"], max_chars=600
    ) == [(0, 600)]
    near_end_source = "Ada arrived. " + "x" * 500 + " Ada departed."
    assert source_excerpt_ranges_around_names(near_end_source, ["Ada"], max_chars=600) == [
        (0, len(near_end_source))
    ]


def test_profile_windows_do_not_treat_lowercase_common_word_as_proper_name():
    from app.utils.characters.text import (
        source_excerpt_range_around_name,
        source_excerpt_ranges_around_names,
    )

    source = "They will return tomorrow. " + "x" * 3_000 + " Will opened the gate."
    windows = source_excerpt_ranges_around_names(source, ["Will"], max_chars=600)

    assert len(windows) == 1
    assert "Will opened the gate." in source[slice(*windows[0])]
    assert "They will return tomorrow." not in source[slice(*windows[0])]
    start, end = source_excerpt_range_around_name(source, "Will", max_chars=600)
    assert start > 0
    assert "Will opened the gate." in source[start:end]
    assert source_excerpt_ranges_around_names("They will return tomorrow.", ["Will"]) == []
    assert source_excerpt_ranges_around_names("WILL opened the gate.", ["Will"])
    assert source_excerpt_ranges_around_names("THE WARDEN spoke.", ["the warden"])


@pytest.mark.asyncio
async def test_collect_chapter_llm_extraction_runs_discovery_then_cited_profile_stage(
    monkeypatch,
):
    book = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4(), language="en")
    passages = ["Mara promised to protect the gate.", "Mara feared the storm."]
    monkeypatch.setattr(
        extraction_chapter_llm_service,
        "_group_chunks_for_extraction",
        lambda _chunks: [[passage] for passage in passages],
    )

    async def fake_discover(_passage, **kwargs):
        assert kwargs["discovery_only"] is True
        return {"characters": [{"name": "Mara", "confidence": 0.9}], "relationships": []}

    async def fake_profile(**kwargs):
        if passages[0] in kwargs["user"]:
            return json.dumps(
                {
                    "profile": {
                        "goal": "protect the gate",
                        "claim_evidence": {"goal": passages[0]},
                    }
                }
            )
        return json.dumps(
            {
                "profile": {
                    "fears": ["the storm"],
                    "claim_evidence": {"fears": {"the storm": passages[1]}},
                }
            }
        )

    monkeypatch.setattr(
        extraction_chapter_llm_service,
        "extract_characters_and_relationships",
        fake_discover,
    )
    monkeypatch.setattr(
        extraction_character_profile_service, "complete_with_fallback", fake_profile
    )

    result = await collect_chapter_llm_extraction(
        object(),
        book=book,
        chapter_number=3,
        chunks=passages,
        existing_characters=[],
    )

    assert result.source_coverage["complete"] is True
    assert result.source_coverage["profile_enrichment"]["status"] == "complete"
    entity = result.aggregated_character_entities[0]
    assert entity["goal"] == "protect the gate"
    assert entity["fears"] == ["the storm"]
    assert entity["evidence"]["profile_claims"]["goal"]["source_batch_key"] == (f"{book.id}:3:1")
    assert entity["evidence"]["profile_claims"]["fears"]["the storm"]["source_batch_key"] == (
        f"{book.id}:3:2"
    )


@pytest.mark.asyncio
async def test_collect_chapter_llm_extraction_marks_unanchored_profile_incomplete(monkeypatch):
    book = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4(), language="en")

    async def fake_discover(_passage, **_kwargs):
        return {
            "characters": [{"name": "Imaginary Person", "confidence": 0.9}],
            "relationships": [],
        }

    async def unexpected_model_call(**_kwargs):
        raise AssertionError("An unanchored name must not trigger profile extraction")

    monkeypatch.setattr(
        extraction_chapter_llm_service,
        "extract_characters_and_relationships",
        fake_discover,
    )
    monkeypatch.setattr(
        extraction_character_profile_service, "complete_with_fallback", unexpected_model_call
    )

    result = await collect_chapter_llm_extraction(
        object(), book=book, chapter_number=1, chunks=["A quiet scene."], existing_characters=[]
    )

    assert result.source_coverage["complete"] is True
    assert result.source_coverage["profile_enrichment"] == {
        "status": "partial",
        "identity_clusters": 1,
        "evidence_passages": 0,
        "unanchored_references": 1,
    }
    assert result.aggregated_character_entities[0]["evidence"]["profile_claims"] == {}
    assert result.raw_character_entities[0]["_source_text"] == ""


@pytest.mark.asyncio
async def test_collect_chapter_llm_extraction_records_invalid_profile_as_partial(monkeypatch):
    book = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4(), language="en")

    async def fake_discover(_passage, **_kwargs):
        return {"characters": [{"name": "Mara", "confidence": 0.9}], "relationships": []}

    async def invalid_profile(**_kwargs):
        return '{"profile":{"goal":"invent a kingdom","claim_evidence":{}}}'

    monkeypatch.setattr(
        extraction_chapter_llm_service, "extract_characters_and_relationships", fake_discover
    )
    monkeypatch.setattr(
        extraction_character_profile_service, "complete_with_fallback", invalid_profile
    )

    result = await collect_chapter_llm_extraction(
        object(),
        book=book,
        chapter_number=2,
        chunks=["Mara arrived at dawn."],
        existing_characters=[],
    )

    assert result.source_coverage["complete"] is True
    assert result.source_coverage["profile_enrichment"]["status"] == "partial"
    assert result.source_coverage["profile_enrichment"]["invalid_response_batches"] == 1
    assert result.aggregated_character_entities[0]["evidence"]["profile_claims"] == {}
    assert (
        result.aggregated_character_entities[0]["evidence"]["profile_enrichment_status"]
        == "partial_invalid_response"
    )


@pytest.mark.asyncio
async def test_collect_chapter_llm_extraction_marks_unexpected_batch_failure_incomplete(
    monkeypatch,
):
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

    monkeypatch.setattr(
        extraction_chapter_llm_service,
        "extract_characters_and_relationships",
        fake_extract,
    )
    with pytest.raises(RuntimeError, match="primary extractor failed"):
        await collect_chapter_llm_extraction(
            object(),
            book=book,
            chapter_number=2,
            chunks=["chunk one"],
            existing_characters=[],
        )


@pytest.mark.asyncio
async def test_failed_character_batch_records_all_outcomes_without_leaking_source(monkeypatch):
    book = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4(), language="en")
    passages = ["Mara crossed the bridge.", "Lina waited near the gate."]
    captured = []

    monkeypatch.setattr(
        extraction_chapter_llm_service,
        "_group_chunks_for_extraction",
        lambda _chunks: [[passage] for passage in passages],
    )

    async def fake_extract(batch_text, **_kwargs):
        if "Lina" in batch_text:
            raise CharacterExtractionFormatError("character_extraction_invalid_response")
        return {"characters": [{"name": "Mara"}], "relationships": []}

    async def record(coverage):
        captured.append(dict(coverage))

    monkeypatch.setattr(
        extraction_chapter_llm_service, "extract_characters_and_relationships", fake_extract
    )
    with pytest.raises(
        CharacterExtractionFormatError, match="character_extraction_invalid_response"
    ):
        await collect_chapter_llm_extraction(
            object(),
            book=book,
            chapter_number=2,
            chunks=passages,
            existing_characters=[],
            on_incomplete_batch=record,
        )

    assert len(captured) == 1
    assert captured[0]["complete"] is False
    assert captured[0]["failure_stage"] == "character_discovery"
    assert captured[0]["batch_outcomes"] == [
        {"batch_index": 1, "status": "succeeded"},
        {"batch_index": 2, "status": "failed", "error_type": "CharacterExtractionFormatError"},
    ]
    assert all(passage not in json.dumps(captured[0]) for passage in passages)


@pytest.mark.asyncio
async def test_failed_profile_enrichment_keeps_discovery_outcomes_and_marks_attempt_incomplete(
    monkeypatch,
):
    book = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4(), language="en")
    captured = []

    async def fake_extract(_batch_text, **_kwargs):
        return {"characters": [{"name": "Mara"}], "relationships": []}

    async def fake_enrich(_entities, **_kwargs):
        raise TimeoutError("model unavailable")

    async def record(coverage):
        captured.append(dict(coverage))

    monkeypatch.setattr(
        extraction_chapter_llm_service, "extract_characters_and_relationships", fake_extract
    )
    monkeypatch.setattr(
        extraction_chapter_llm_service, "enrich_chapter_character_profiles", fake_enrich
    )

    with pytest.raises(TimeoutError, match="model unavailable"):
        await collect_chapter_llm_extraction(
            object(),
            book=book,
            chapter_number=1,
            chunks=["Mara entered the courtyard."],
            existing_characters=[],
            on_incomplete_batch=record,
        )

    assert captured[0]["complete"] is False
    assert captured[0]["failure_stage"] == "character_profile_enrichment"
    assert captured[0]["batch_outcomes"] == [{"batch_index": 1, "status": "succeeded"}]
    assert captured[0]["profile_enrichment"] == {"status": "failed", "error_type": "TimeoutError"}


@pytest.mark.asyncio
async def test_collect_chapter_llm_extraction_does_not_fallback_on_provider_failure(monkeypatch):
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

    async def fake_extract(*_args, **_kwargs):
        raise APIConnectionError(
            request=Request("POST", "https://api.openai.com/v1/chat/completions")
        )

    monkeypatch.setattr(
        extraction_chapter_llm_service,
        "extract_characters_and_relationships",
        fake_extract,
    )
    with pytest.raises(APIConnectionError):
        await collect_chapter_llm_extraction(
            object(),
            book=book,
            chapter_number=2,
            chunks=["chunk one"],
            existing_characters=[],
        )


@pytest.mark.asyncio
async def test_collect_chapter_llm_extraction_does_not_mark_invalid_model_output_complete(
    monkeypatch,
):
    book = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4(), language="en")
    monkeypatch.setattr(
        extraction_chapter_llm_service,
        "_group_chunks_for_extraction",
        lambda _chunks: [["scene"]],
    )
    monkeypatch.setattr(
        extraction_chapter_llm_service, "build_character_roster_snapshot", lambda _items: []
    )

    async def fake_extract(*_args, **_kwargs):
        raise CharacterExtractionFormatError("character_extraction_invalid_response")

    monkeypatch.setattr(
        extraction_chapter_llm_service, "extract_characters_and_relationships", fake_extract
    )
    with pytest.raises(CharacterExtractionFormatError):
        await collect_chapter_llm_extraction(
            object(), book=book, chapter_number=1, chunks=["scene"], existing_characters=[]
        )


@pytest.mark.asyncio
async def test_overlapping_extraction_batches_count_one_source_mention_once(monkeypatch):
    from app.services import extraction_processing_flow_service

    book = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4(), language="en")
    source = "x" * 22 + " Mara " + "y" * 45
    monkeypatch.setattr(
        extraction_processing_flow_service.settings, "EXTRACTION_BATCH_MAX_TOKENS", 30
    )
    monkeypatch.setattr(
        extraction_processing_flow_service.settings, "EXTRACTION_BATCH_MAX_CHUNKS", 1
    )
    monkeypatch.setattr(extraction_processing_flow_service, "count_tokens", len)
    monkeypatch.setattr(extraction_chapter_llm_service, "count_tokens", len)

    async def discover(passage, **_kwargs):
        return {
            "characters": [
                {
                    "name": "Mara",
                    "confidence": 0.9,
                    "evidence": {"mention_count": 1, "strong_mention_count": 1},
                }
            ]
            if "Mara" in passage
            else [],
            "relationships": [],
        }

    async def enrich(entities, **_kwargs):
        return entities

    monkeypatch.setattr(
        extraction_chapter_llm_service, "extract_characters_and_relationships", discover
    )
    monkeypatch.setattr(extraction_chapter_llm_service, "enrich_chapter_character_profiles", enrich)

    result = await collect_chapter_llm_extraction(
        object(), book=book, chapter_number=1, chunks=[source], existing_characters=[]
    )

    assert result.source_coverage["complete"] is True
    assert len(result.raw_character_entities) == 2
    assert result.raw_character_entities[0]["_source_mentions"] == [
        {"chunk_index": 0, "start": 23, "end": 27}
    ]
    assert (
        result.raw_character_entities[1]["_source_mentions"]
        == result.raw_character_entities[0]["_source_mentions"]
    )
    assert result.aggregated_character_entities[0]["evidence"]["mention_count"] == 1
    assert result.aggregated_character_entities[0]["evidence"]["strong_mention_count"] == 1
    assert (
        result.aggregated_character_entities[0]["evidence"]["source_mention_count_verified"] is True
    )


@pytest.mark.asyncio
async def test_extraction_uses_source_mentions_not_inflated_model_count(monkeypatch):
    book = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4(), language="en")

    async def discover(_passage, **_kwargs):
        return {
            "characters": [
                {
                    "name": "Mara",
                    "confidence": 0.9,
                    "evidence": {"mention_count": 7, "strong_mention_count": 5},
                }
            ],
            "relationships": [],
        }

    async def enrich(entities, **_kwargs):
        return entities

    monkeypatch.setattr(
        extraction_chapter_llm_service, "extract_characters_and_relationships", discover
    )
    monkeypatch.setattr(extraction_chapter_llm_service, "enrich_chapter_character_profiles", enrich)

    result = await collect_chapter_llm_extraction(
        object(),
        book=book,
        chapter_number=1,
        chunks=["Mara waited beside the gate."],
        existing_characters=[],
    )

    assert result.aggregated_character_entities[0]["evidence"]["mention_count"] == 1
    assert result.aggregated_character_entities[0]["evidence"]["strong_mention_count"] == 1
    assert (
        result.aggregated_character_entities[0]["evidence"]["source_mention_count_verified"] is True
    )
