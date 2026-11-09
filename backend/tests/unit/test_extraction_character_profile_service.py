import json
import uuid

import pytest
from fastapi import HTTPException

from app.services import extraction_character_profile_service
from app.services.extraction_character_profile_service import (
    PROFILE_SYSTEM,
    CharacterProfileFormatError,
    enrich_chapter_character_profiles,
    extract_profile_from_packet,
)
from app.utils.characters.profile_evidence import PROFILE_SCALAR_FIELDS
from app.utils.llm_usage_utils import LLMIncompleteResponseError


def test_profile_prompt_requests_evidence_for_every_supported_scalar_claim():
    example_text = PROFILE_SYSTEM.split("Return JSON only: ", 1)[1].split(".\nTrait values", 1)[0]
    example = json.loads(example_text)["profile"]
    assert set(PROFILE_SCALAR_FIELDS) <= set(example["claim_evidence"])
    assert set(PROFILE_SCALAR_FIELDS) <= set(example)


@pytest.mark.asyncio
async def test_profile_packet_requires_verbatim_claim_and_preserves_batch_offsets(monkeypatch):
    source = "Mara promised to protect the gate."
    calls = []

    async def fake_complete(**kwargs):
        calls.append(kwargs)
        return json.dumps(
            {
                "profile": {
                    "goal": "protect the gate",
                    "claim_evidence": {"goal": source},
                }
            }
        )

    monkeypatch.setattr(
        extraction_character_profile_service, "complete_with_fallback", fake_complete
    )
    result = await extract_profile_from_packet(
        character_name="Mara",
        aliases=[],
        packet={"text": source, "source_batch_key": "book:1:2", "source_start": 125},
        user_id=uuid.uuid4(),
        book_id=uuid.uuid4(),
        language="en",
    )

    assert result["goal"] == "protect the gate"
    assert result["evidence"]["profile_claims"]["goal"]["start"] == 125
    assert result["_source_batch_key"] == "book:1:2"
    assert len(calls) == 1
    assert calls[0]["usage_feature"] == "character_profile_enrichment"
    assert source in calls[0]["user"]


@pytest.mark.asyncio
async def test_profile_packet_preserves_cited_first_appearance_and_backstory(monkeypatch):
    source = "Mara entered the station. The fire had destroyed her home."

    async def fake_complete(**_kwargs):
        return json.dumps(
            {
                "profile": {
                    "first_appearance_context": "entered the station",
                    "backstory_wound": "lost her home in a fire",
                    "claim_evidence": {
                        "first_appearance_context": "Mara entered the station.",
                        "backstory_wound": "The fire had destroyed her home.",
                    },
                }
            }
        )

    monkeypatch.setattr(
        extraction_character_profile_service, "complete_with_fallback", fake_complete
    )
    result = await extract_profile_from_packet(
        character_name="Mara",
        aliases=[],
        packet={"text": source, "source_batch_key": "book:1:1", "source_start": 80},
        user_id=uuid.uuid4(),
        book_id=uuid.uuid4(),
        language="en",
    )

    assert result["first_appearance_context"] == "entered the station"
    assert result["backstory_wound"] == "lost her home in a fire"
    assert result["evidence"]["profile_claims"]["first_appearance_context"]["start"] == 80
    assert result["evidence"]["profile_claims"]["backstory_wound"]["start"] > 80


@pytest.mark.asyncio
async def test_profile_packet_rejects_two_truncated_model_answers(monkeypatch):
    calls = []

    async def fake_complete(**kwargs):
        calls.append(kwargs)
        raise LLMIncompleteResponseError("llm_response_incomplete")

    monkeypatch.setattr(
        extraction_character_profile_service, "complete_with_fallback", fake_complete
    )
    with pytest.raises(CharacterProfileFormatError, match="character_profile_invalid"):
        await extract_profile_from_packet(
            character_name="Mara",
            aliases=[],
            packet={
                "text": "Mara watched the gate.",
                "source_batch_key": "book:1:1",
                "source_start": 0,
            },
            user_id=uuid.uuid4(),
            book_id=uuid.uuid4(),
            language="en",
        )

    assert len(calls) == 2
    assert all(call["require_complete_output"] is True for call in calls)


@pytest.mark.asyncio
async def test_profile_packet_retries_short_slot_contention_without_restarting_chapter(
    monkeypatch,
):
    calls = 0

    async def fake_complete(**_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise HTTPException(
                429,
                "LLM capacity is temporarily busy. Retry shortly.",
                headers={"Retry-After": "0.01"},
            )
        return '{"profile": {"goal": null, "claim_evidence": {}}}'

    monkeypatch.setattr(
        extraction_character_profile_service, "complete_with_fallback", fake_complete
    )
    result = await extract_profile_from_packet(
        character_name="Mara",
        aliases=[],
        packet={
            "text": "Mara crossed the bridge.",
            "source_batch_key": "book:1:1",
            "source_start": 0,
        },
        user_id=uuid.uuid4(),
        book_id=uuid.uuid4(),
        language="en",
    )

    assert calls == 2
    assert result["_source_batch_key"] == "book:1:1"


@pytest.mark.asyncio
async def test_profile_packet_does_not_retry_monthly_budget_denial(monkeypatch):
    calls = 0

    async def fake_complete(**_kwargs):
        nonlocal calls
        calls += 1
        raise HTTPException(429, {"kind": "llm_budget", "message": "Monthly AI budget reached."})

    monkeypatch.setattr(
        extraction_character_profile_service, "complete_with_fallback", fake_complete
    )
    with pytest.raises(HTTPException) as caught:
        await extract_profile_from_packet(
            character_name="Mara",
            aliases=[],
            packet={
                "text": "Mara crossed the bridge.",
                "source_batch_key": "book:1:1",
                "source_start": 0,
            },
            user_id=uuid.uuid4(),
            book_id=uuid.uuid4(),
            language="en",
        )

    assert caught.value.detail["kind"] == "llm_budget"
    assert calls == 1


@pytest.mark.asyncio
async def test_profile_packet_stops_after_one_transient_timeout_retry(monkeypatch):
    calls = 0

    async def fake_complete(**_kwargs):
        nonlocal calls
        calls += 1
        raise TimeoutError("temporary provider timeout")

    monkeypatch.setattr(
        extraction_character_profile_service, "complete_with_fallback", fake_complete
    )
    with pytest.raises(TimeoutError, match="temporary provider timeout"):
        await extract_profile_from_packet(
            character_name="Mara",
            aliases=[],
            packet={
                "text": "Mara crossed the bridge.",
                "source_batch_key": "book:1:1",
                "source_start": 0,
            },
            user_id=uuid.uuid4(),
            book_id=uuid.uuid4(),
            language="en",
        )

    assert calls == 2


@pytest.mark.asyncio
async def test_profile_enrichment_merges_independent_evidence_passages(monkeypatch):
    async def fake_complete(**kwargs):
        if "Mara promised" in kwargs["user"]:
            return json.dumps(
                {
                    "profile": {
                        "goal": "protect the gate",
                        "claim_evidence": {"goal": "Mara promised to protect the gate."},
                    }
                }
            )
        return json.dumps(
            {
                "profile": {
                    "fears": ["the storm"],
                    "claim_evidence": {"fears": {"the storm": "Mara feared the storm."}},
                }
            }
        )

    monkeypatch.setattr(
        extraction_character_profile_service, "complete_with_fallback", fake_complete
    )
    entity = {
        "name": "Mara",
        "aliases": [],
        "evidence": {"mention_count": 2},
        "cluster_members": [
            {
                "source_batch_key": "book:1:1",
                "source_start": 30,
                "source_text": "Mara promised to protect the gate.",
            },
            {
                "source_batch_key": "book:1:2",
                "source_start": 80,
                "source_text": "Mara feared the storm.",
            },
        ],
    }

    result = await enrich_chapter_character_profiles(
        [entity], user_id=uuid.uuid4(), book_id=uuid.uuid4(), language="en"
    )

    assert result[0]["goal"] == "protect the gate"
    assert result[0]["fears"] == ["the storm"]
    assert result[0]["evidence"]["mention_count"] == 2
    assert result[0]["evidence"]["profile_claims"]["goal"]["source_batch_key"] == "book:1:1"
    assert result[0]["evidence"]["profile_claims"]["fears"]["the storm"]["start"] == 80


@pytest.mark.asyncio
async def test_profile_enrichment_bundles_same_batch_windows_without_losing_late_evidence(
    monkeypatch,
):
    calls = 0

    async def fake_complete(**kwargs):
        nonlocal calls
        calls += 1
        assert "Mara arrived." in kwargs["user"]
        assert "Mara feared the storm." in kwargs["user"]
        return json.dumps(
            {
                "profile": {
                    "fears": ["the storm"],
                    "claim_evidence": {"fears": {"the storm": "Mara feared the storm."}},
                }
            }
        )

    monkeypatch.setattr(
        extraction_character_profile_service, "complete_with_fallback", fake_complete
    )
    entity = {
        "name": "Mara",
        "cluster_members": [
            {
                "source_batch_key": "book:1:1",
                "source_windows": [
                    {"start": 0, "text": "Mara arrived."},
                    {"start": 3000, "text": "Mara feared the storm."},
                ],
            }
        ],
    }

    enriched = await enrich_chapter_character_profiles(
        [entity], user_id=uuid.uuid4(), book_id=uuid.uuid4(), language="en"
    )

    assert calls == 1
    assert enriched[0]["fears"] == ["the storm"]
    assert enriched[0]["evidence"]["profile_claims"]["fears"]["the storm"]["start"] == 3000


@pytest.mark.asyncio
async def test_profile_enrichment_retries_invalid_output_and_fails_visibly(monkeypatch):
    attempts = 0
    prompts = []

    async def fake_complete(**kwargs):
        nonlocal attempts
        attempts += 1
        prompts.append(kwargs["user"])
        return json.dumps({"profile": {"goal": "invent a kingdom", "claim_evidence": {}}})

    monkeypatch.setattr(
        extraction_character_profile_service, "complete_with_fallback", fake_complete
    )
    packet = {"text": "Mara arrived.", "source_batch_key": "book:1:1", "source_start": 0}
    with pytest.raises(CharacterProfileFormatError, match="unsupported_response"):
        await extract_profile_from_packet(
            character_name="Mara",
            aliases=[],
            packet=packet,
            user_id=uuid.uuid4(),
            book_id=uuid.uuid4(),
            language="en",
        )
    assert attempts == 2
    assert "Validation feedback" not in prompts[0]
    assert "lacked a verbatim quote" in prompts[1]


@pytest.mark.asyncio
async def test_profile_enrichment_does_not_accept_malformed_claims_as_empty_success(monkeypatch):
    attempts = 0

    async def fake_complete(**_kwargs):
        nonlocal attempts
        attempts += 1
        return json.dumps(
            {
                "profile": {
                    "fears": [{"label": "the sea"}],
                    "claim_evidence": {},
                }
            }
        )

    monkeypatch.setattr(
        extraction_character_profile_service, "complete_with_fallback", fake_complete
    )

    with pytest.raises(CharacterProfileFormatError, match="unsupported_response"):
        await extract_profile_from_packet(
            character_name="Mara",
            aliases=[],
            packet={
                "text": "Mara watched the sea.",
                "source_batch_key": "book:1:1",
                "source_start": 0,
            },
            user_id=uuid.uuid4(),
            book_id=uuid.uuid4(),
            language="en",
        )

    assert attempts == 2


@pytest.mark.asyncio
async def test_profile_enrichment_retry_accepts_only_cited_correction(monkeypatch):
    source = "Mara promised to protect the gate."
    prompts = []

    async def fake_complete(**kwargs):
        prompts.append(kwargs["user"])
        if len(prompts) == 1:
            return json.dumps({"profile": {"goal": "invent a kingdom", "claim_evidence": {}}})
        return json.dumps(
            {
                "profile": {
                    "goal": "protect the gate",
                    "claim_evidence": {"goal": source},
                }
            }
        )

    monkeypatch.setattr(
        extraction_character_profile_service, "complete_with_fallback", fake_complete
    )
    result = await extract_profile_from_packet(
        character_name="Mara",
        aliases=[],
        packet={"text": source, "source_batch_key": "book:1:1", "source_start": 0},
        user_id=uuid.uuid4(),
        book_id=uuid.uuid4(),
        language="en",
    )

    assert len(prompts) == 2
    assert "Validation feedback" in prompts[1]
    assert result["goal"] == "protect the gate"
    assert result["evidence"]["profile_claims"]["goal"]["quote"] == source


@pytest.mark.asyncio
async def test_profile_enrichment_marks_unanchored_reference_without_model_call():
    kwargs = {"user_id": uuid.uuid4(), "book_id": uuid.uuid4(), "language": "en"}

    assert await enrich_chapter_character_profiles([], **kwargs) == []
    result = await enrich_chapter_character_profiles(
        [
            {
                "name": "Mara",
                "evidence": {"mention_count": 1},
                "cluster_members": [{"source_windows": []}],
            }
        ],
        **kwargs,
    )
    assert result[0]["goal"] is None
    assert result[0]["evidence"]["profile_claims"] == {}
    assert result[0]["evidence"]["profile_enrichment_status"] == "unanchored_reference"
