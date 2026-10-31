import json
import uuid
from copy import deepcopy
from types import SimpleNamespace

import pytest
from httpx import Request, Response
from openai import APIConnectionError, APIStatusError
from sqlalchemy import select

from app.api.v1.routes.advisor import voice
from app.core.security import create_access_token
from app.models.book import Book
from app.models.character import Character, CharacterVoiceProfile, VoiceReviewDecision
from app.models.user import User
from app.services.data_generation_service import (
    create_staging_generation,
    promote_staging_generation,
)
from app.services.extraction_voice_profile_service import refresh_chapter_voice_profiles
from app.services.voice_consistency_review_service import (
    VoiceBaselineSourceError,
    load_voice_review_characters,
)
from app.utils.request_context import get_request_id


@pytest.mark.asyncio
async def test_collaborator_passage_review_bills_owner_and_keeps_reviewer_decisions(
    client, db, auth_headers, monkeypatch
):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    owner_id = uuid.UUID(me.json()["id"])
    reviewer = User(email=f"voice-reviewer-{uuid.uuid4()}@example.test", password_hash="test")
    db.add(reviewer)
    book = Book(
        user_id=owner_id,
        title="Shared voice review",
        format="manual",
        work_type="novel",
        s3_key="books/shared-voice.txt",
        status="ready",
        mode="author",
    )
    db.add(book)
    await db.commit()

    async def access(*_args, **_kwargs):
        return book, SimpleNamespace(role="editor", scope={}, permissions={}), None

    async def version(*_args):
        return 3

    captured = {}

    async def review(**kwargs):
        captured.update(kwargs)
        return {"review": {"status": "insufficient_evidence"}}

    monkeypatch.setattr(voice, "get_book_with_ai_scan_access", access)
    monkeypatch.setattr(voice, "get_book_cache_version", version)
    monkeypatch.setattr(voice, "run_voice_consistency_review", review)
    headers = {"Authorization": f"Bearer {create_access_token(str(reviewer.id))}"}
    response = await client.post(
        f"/api/v1/intelligence/{book.id}/advisor/voice-consistency",
        headers=headers,
        json={"text": "A short revision", "chapter_num": 2},
    )
    assert response.status_code == 200
    assert captured["current_user"].id == reviewer.id
    assert captured["billing_user"].id == owner_id


@pytest.mark.asyncio
async def test_reprocessed_voice_profile_stays_hidden_until_its_character_generation_is_active(
    client, db, auth_headers
):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = uuid.UUID(me.json()["id"])
    book = Book(
        user_id=user_id,
        title="Staged voice",
        format="manual",
        work_type="novel",
        s3_key="books/staged-voice.txt",
        status="ready",
        mode="author",
    )
    db.add(book)
    await db.flush()
    rebuild_run_id = uuid.uuid4().hex
    generation_id = await create_staging_generation(
        db, book_id=book.id, rebuild_run_id=rebuild_run_id, reason="voice_profile_test"
    )
    character = Character(
        book_id=book.id,
        generation_id=generation_id,
        name="Mara",
        first_chapter=1,
        mention_count=1,
        visibility_state="visible",
        approval_state="approved",
    )
    db.add(character)
    await db.flush()
    assert (
        await refresh_chapter_voice_profiles(
            db,
            book=book,
            chapter_text='Mara said, "I shall return before dawn."',
            existing_characters=[character],
        )
        == 1
    )
    await db.commit()
    assert (
        await refresh_chapter_voice_profiles(
            db,
            book=book,
            chapter_text='Mara replied, "I shall return before dawn."',
            existing_characters=[character],
        )
        == 1
    )
    await db.commit()
    staged = (
        (
            await db.execute(
                select(CharacterVoiceProfile)
                .where(CharacterVoiceProfile.book_id == book.id)
                .execution_options(include_all_generations=True)
            )
        )
        .scalars()
        .all()
    )
    assert len(staged) == 1
    assert staged[0].generation_id == generation_id
    assert staged[0].sample_dialogue_count == 2
    assert (
        await db.execute(
            select(CharacterVoiceProfile).where(CharacterVoiceProfile.book_id == book.id)
        )
    ).scalars().all() == []

    assert await promote_staging_generation(db, book_id=book.id, rebuild_run_id=rebuild_run_id)
    await db.commit()
    active = (
        (
            await db.execute(
                select(CharacterVoiceProfile).where(CharacterVoiceProfile.book_id == book.id)
            )
        )
        .scalars()
        .all()
    )
    assert [item.id for item in active] == [staged[0].id]


@pytest.mark.asyncio
async def test_voice_review_uses_only_visible_cast_for_detection_and_selection(
    client, db, auth_headers, monkeypatch
):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = uuid.UUID(me.json()["id"])
    book = Book(
        user_id=user_id,
        title="Visible voices",
        format="manual",
        work_type="novel",
        s3_key="books/visible-voices.txt",
        status="ready",
        mode="author",
    )
    db.add(book)
    await db.flush()
    visible = Character(
        book_id=book.id,
        name="Mara",
        role="mc",
        first_chapter=1,
        mention_count=8,
        visibility_state="visible",
        approval_state="approved",
    )
    hidden = Character(
        book_id=book.id,
        name="Specter",
        role="sc",
        first_chapter=1,
        mention_count=100,
        visibility_state="quarantined",
        approval_state="pending_review",
    )
    db.add_all([visible, hidden])
    await db.flush()
    merged = Character(
        book_id=book.id,
        name="Mara Old",
        role="sc",
        first_chapter=1,
        mention_count=200,
        visibility_state="visible",
        approval_state="approved",
        merged_into_character_id=visible.id,
    )
    db.add(merged)
    await db.commit()

    cast = await load_voice_review_characters(db, book_id=book.id)
    assert [character["name"] for character in cast] == ["Mara"]

    async def fake_context(*_args, **_kwargs):
        return "Story context"

    monkeypatch.setattr(
        "app.services.voice_consistency_orchestration_service.build_story_context", fake_context
    )
    submitted = 'Specter said, "Leave now." Mara replied, "We will stay."'
    detected = await client.post(
        f"/api/v1/intelligence/{book.id}/advisor/voice-consistency",
        headers=auth_headers,
        json={"text": submitted, "chapter_num": 2},
    )
    assert detected.status_code == 200
    assert detected.json()["review"]["status"] == "insufficient_evidence"
    assert detected.json()["characters_detected"] == ["Mara"]

    for excluded in (hidden, merged):
        selected = await client.post(
            f"/api/v1/intelligence/{book.id}/advisor/voice-consistency",
            headers=auth_headers,
            json={
                "text": submitted,
                "chapter_num": 2,
                "character_id": str(excluded.id),
            },
        )
        assert selected.status_code == 400


class _FakeOpenAIClient:
    def __init__(self):
        self.close_calls = 0

    async def close(self):
        self.close_calls += 1


@pytest.mark.asyncio
async def test_first_person_auto_detect_reviews_only_explicitly_named_narrator(
    client, db, auth_headers, monkeypatch
):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    book = Book(
        user_id=uuid.UUID(me.json()["id"]),
        title="Named narrator",
        format="manual",
        work_type="novel",
        s3_key="books/named-narrator.txt",
        status="ready",
        mode="author",
    )
    db.add(book)
    await db.flush()
    narrators = [
        Character(
            book_id=book.id,
            name=name,
            role="mc",
            first_chapter=1,
            mention_count=8,
            visibility_state="visible",
            approval_state="approved",
        )
        for name in ("Mara", "Lina")
    ]
    db.add_all(narrators)
    await db.commit()

    async def fake_context(*_args, **_kwargs):
        return "Story context"

    async def fake_baseline(*_args, **_kwargs):
        return [
            {
                "chapter_number": chapter,
                "excerpt": "I carried the notebook along the river and waited for the lamps to turn on. "
                * 4,
                "source_id": f"baseline-{chapter}",
                "attribution_confidence": "explicit",
            }
            for chapter in (1, 2, 3)
        ]

    reviewed: list[str] = []

    async def fake_review(passage, *, character_name, **_kwargs):
        reviewed.append(character_name)
        return {
            "issues": (
                [
                    {
                        "character_name": character_name,
                        "classification": "confirmed",
                        "confidence": 0.95,
                        "submitted_excerpt": "I counted the empty boats",
                        "baseline_excerpt": "I carried the notebook along the river",
                        "baseline_chapter_number": 1,
                    }
                ]
                if "I counted the empty boats" in passage
                else []
            ),
            "overall_verdict": (
                "Potential narrator voice difference."
                if "I counted the empty boats" in passage
                else "No supported difference in the narrator's prose."
            ),
            "coverage": {
                "processed_ranges": [{"start": 0, "end": len(passage)}],
                "unattributed_ranges": [],
                "compared_ranges": [{"start": 0, "end": len(passage)}],
                "total_characters": len(passage),
            },
        }

    async def no_cache(*_args, **_kwargs):
        return None

    monkeypatch.setattr(
        "app.services.voice_consistency_orchestration_service.build_story_context", fake_context
    )
    monkeypatch.setattr(
        "app.services.voice_consistency_orchestration_service.load_voice_baseline_samples",
        fake_baseline,
    )
    monkeypatch.setattr(
        "app.services.voice_consistency_orchestration_service.review_voice_sections", fake_review
    )
    monkeypatch.setattr(
        "app.services.voice_consistency_orchestration_service.get_openai_client", _FakeOpenAIClient
    )
    monkeypatch.setattr(
        "app.services.voice_consistency_orchestration_service.get_voice_consistency_cache", no_cache
    )
    monkeypatch.setattr(
        "app.services.voice_consistency_orchestration_service.set_voice_consistency_cache", no_cache
    )
    passage = (
        "I am Mara. I crossed the station before dawn with a folded map in my pocket. "
        "I looked for the northbound train, but I saw only a dark platform and a locked gate. "
        "I waited beside the ticket window until the lamps came on. I kept the map dry."
    )
    url = f"/api/v1/intelligence/{book.id}/advisor/voice-consistency"
    response = await client.post(
        url,
        headers=auth_headers,
        json={
            "text": passage,
            "chapter_num": 4,
            "voice_mode": "first_person_narration",
        },
    )
    assert response.status_code == 200
    assert response.json()["characters_detected"] == ["Mara"]
    assert response.json()["characters_reviewed"] == ["Mara"]
    assert response.json()["baseline_evidence"][0]["attribution_confidence"] == "explicit"
    assert reviewed == ["Mara"]

    contextual_passage = (
        'The clerk said, "I will leave you here, Mara." I thanked her and walked on. '
        "I carried the notebook along the river before dawn and waited for the lamps to turn on. "
        "I counted the empty boats, watched the water rise under the bridge, and kept my map dry. "
        "I did not speak to anyone else before I reached the locked station gate."
    )
    contextual = await client.post(
        url,
        headers=auth_headers,
        json={
            "text": contextual_passage,
            "chapter_num": 4,
            "voice_mode": "first_person_narration",
        },
    )
    assert contextual.status_code == 200
    contextual_payload = contextual.json()
    assert contextual_payload["characters_detected"] == ["Mara"]
    assert contextual_payload["review"]["status"] == "partial_evidence"
    assert contextual_payload["character_matches"] == []
    assert contextual_payload["review"]["issues"][0]["classification"] == "possible"
    assert contextual_payload["review"]["issues"][0]["confidence"] == 0.75
    assert contextual_payload["baseline_evidence"][0]["baseline_attribution_confidence"] == (
        "explicit"
    )
    assert contextual_payload["baseline_evidence"][0]["attribution_confidence"] == "contextual"
    assert any("tentative" in warning.lower() for warning in contextual_payload["warnings"])
    assert reviewed == ["Mara", "Mara"]

    ambiguous_address = await client.post(
        url,
        headers=auth_headers,
        json={
            "text": '"You, Mara." I nodded. Later, "You, Lina." I answered.',
            "chapter_num": 4,
            "voice_mode": "first_person_narration",
        },
    )
    assert ambiguous_address.status_code == 200
    assert ambiguous_address.json()["review"]["status"] == "insufficient_evidence"
    assert ambiguous_address.json()["characters_detected"] == []
    assert reviewed == ["Mara", "Mara"]

    ambiguous = await client.post(
        url,
        headers=auth_headers,
        json={
            "text": "I am Mara. Later I am Lina. I crossed the station alone.",
            "chapter_num": 4,
            "voice_mode": "first_person_narration",
        },
    )
    assert ambiguous.status_code == 200
    assert ambiguous.json()["review"]["status"] == "insufficient_evidence"
    assert ambiguous.json()["characters_detected"] == []
    assert "no identity was guessed" in " ".join(ambiguous.json()["warnings"]).lower()
    assert reviewed == ["Mara", "Mara"]

    selected_mixed = await client.post(
        url,
        headers=auth_headers,
        json={
            "text": "I am Mara. Later I am Lina. I crossed the station alone.",
            "chapter_num": 4,
            "character_id": str(narrators[0].id),
            "voice_mode": "first_person_narration",
        },
    )
    assert selected_mixed.status_code == 200
    assert selected_mixed.json()["review"]["status"] == "insufficient_evidence"
    assert any(
        "more than one first-person narrator" in warning
        for warning in selected_mixed.json()["warnings"]
    )
    assert reviewed == ["Mara", "Mara"]

    selected_wrong = await client.post(
        url,
        headers=auth_headers,
        json={
            "text": "I am Lina. I crossed the station alone and kept my map dry.",
            "chapter_num": 4,
            "character_id": str(narrators[0].id),
            "voice_mode": "first_person_narration",
        },
    )
    assert selected_wrong.status_code == 200
    assert selected_wrong.json()["review"]["status"] == "insufficient_evidence"
    assert any(
        "different first-person narrator" in warning
        for warning in selected_wrong.json()["warnings"]
    )
    assert reviewed == ["Mara", "Mara"]


@pytest.mark.asyncio
async def test_dialogue_review_attributes_first_person_speech_to_explicit_narrator(
    client, db, auth_headers, monkeypatch
):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    book = Book(
        user_id=uuid.UUID(me.json()["id"]),
        title="Named first-person dialogue",
        format="manual",
        work_type="novel",
        s3_key="books/named-first-person-dialogue.txt",
        status="ready",
        mode="author",
    )
    db.add(book)
    await db.flush()
    db.add(
        Character(
            book_id=book.id,
            name="Mara Vale",
            role="mc",
            first_chapter=1,
            mention_count=5,
            visibility_state="visible",
            approval_state="approved",
        )
    )
    await db.commit()
    passage = (
        'I am Mara Vale. I said, "Keep the lamps low until we reach the far gate '
        'and see whether the watchmen have left." '
        '"Do not open it before I return with the key from the tower," I replied.'
    )
    observed: list[list[str]] = []

    async def fake_context(*_args, **_kwargs):
        return "Story context"

    async def fake_baseline(*_args, **_kwargs):
        return [
            {
                "chapter_number": number,
                "excerpt": "I will inspect the gate before anyone moves the lanterns. " * 2,
                "source_id": f"baseline-{number}",
            }
            for number in (1, 2, 3)
        ]

    async def fake_review(passage_text, *, submitted_samples, **_kwargs):
        assert passage_text == passage
        observed.append([sample["excerpt"] for sample in submitted_samples])
        return {
            "issues": [],
            "overall_verdict": "No supported difference in the attributed dialogue.",
            "coverage": {
                "processed_ranges": [{"start": 0, "end": len(passage)}],
                "unattributed_ranges": [],
                "compared_ranges": [
                    {"start": sample["source_start"], "end": sample["source_end"]}
                    for sample in submitted_samples
                ],
                "total_characters": len(passage),
            },
        }

    async def no_cache(*_args, **_kwargs):
        return None

    async def no_store(*_args, **_kwargs):
        return None

    monkeypatch.setattr(
        "app.services.voice_consistency_orchestration_service.build_story_context", fake_context
    )
    monkeypatch.setattr(
        "app.services.voice_consistency_orchestration_service.load_voice_baseline_samples",
        fake_baseline,
    )
    monkeypatch.setattr(
        "app.services.voice_consistency_orchestration_service.review_voice_sections", fake_review
    )
    monkeypatch.setattr(
        "app.services.voice_consistency_orchestration_service.get_openai_client", _FakeOpenAIClient
    )
    monkeypatch.setattr(
        "app.services.voice_consistency_orchestration_service.get_voice_consistency_cache", no_cache
    )
    monkeypatch.setattr(
        "app.services.voice_consistency_orchestration_service.set_voice_consistency_cache", no_store
    )

    response = await client.post(
        f"/api/v1/intelligence/{book.id}/advisor/voice-consistency",
        headers=auth_headers,
        json={"text": passage, "chapter_num": 4, "voice_mode": "dialogue"},
    )

    assert response.status_code == 200
    assert observed == [
        [
            "Keep the lamps low until we reach the far gate and see whether the watchmen have left.",
            "Do not open it before I return with the key from the tower,",
        ]
    ]
    assert response.json()["review"]["status"] == "complete"


@pytest.mark.asyncio
async def test_voice_review_aggregates_coverage_across_two_detected_characters(
    client, db, auth_headers, monkeypatch
):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    book = Book(
        user_id=uuid.UUID(me.json()["id"]),
        title="Two voices",
        format="manual",
        work_type="novel",
        s3_key="books/two-voices.txt",
        status="ready",
        mode="author",
    )
    db.add(book)
    await db.flush()
    db.add_all(
        [
            Character(
                book_id=book.id,
                name=name,
                role="sc",
                first_chapter=1,
                mention_count=5,
                visibility_state="visible",
                approval_state="approved",
            )
            for name in ("Mara", "Lio")
        ]
    )
    await db.commit()

    submitted = (
        'Mara said, "I will wait by the bridge until the rain stops tonight." '
        'Lio replied, "I will search the north bank before morning arrives."'
    )
    midpoint = len(submitted) // 2
    leave_gap = False
    leave_quote_unattributed = False

    async def fake_context(*_args, **_kwargs):
        return "Story context"

    async def fake_baseline(*_args, **_kwargs):
        return [
            {
                "chapter_number": chapter,
                "excerpt": "I will stand beside the river and watch the weather change tonight. "
                * 3,
                "source_id": f"baseline-{chapter}",
            }
            for chapter in (1, 2, 3)
        ]

    async def fake_review(passage, *, character_name, **_kwargs):
        assert passage == submitted
        processed = (
            {"start": 0, "end": midpoint}
            if character_name == "Mara"
            else {"start": midpoint, "end": len(submitted) - (10 if leave_gap else 0)}
        )
        unattributed = (
            [{"start": midpoint, "end": len(submitted)}]
            if character_name == "Mara"
            else [
                {"start": 0, "end": midpoint},
                *([{"start": len(submitted) - 10, "end": len(submitted)}] if leave_gap else []),
            ]
        )
        quote_text = (
            "I will wait by the bridge until the rain stops tonight."
            if character_name == "Mara"
            else "I will search the north bank before morning arrives."
        )
        quote_start = submitted.index(quote_text)
        quote_end = min(quote_start + len(quote_text), processed["end"])
        compared = (
            []
            if character_name == "Lio" and leave_quote_unattributed
            else [{"start": quote_start, "end": quote_end}]
        )
        return {
            "issues": [],
            "overall_verdict": "No supported difference in attributed dialogue.",
            "coverage": {
                "processed_ranges": [processed],
                "unattributed_ranges": unattributed,
                "compared_ranges": compared,
                "total_characters": len(submitted),
            },
        }

    async def no_cache(*_args, **_kwargs):
        return None

    cached_payloads = []

    async def record_cache(*args, **_kwargs):
        cached_payloads.append(args[2])

    monkeypatch.setattr(
        "app.services.voice_consistency_orchestration_service.build_story_context", fake_context
    )
    monkeypatch.setattr(
        "app.services.voice_consistency_orchestration_service.load_voice_baseline_samples",
        fake_baseline,
    )
    monkeypatch.setattr(
        "app.services.voice_consistency_orchestration_service.review_voice_sections", fake_review
    )
    monkeypatch.setattr(
        "app.services.voice_consistency_orchestration_service.get_openai_client", _FakeOpenAIClient
    )
    monkeypatch.setattr(
        "app.services.voice_consistency_orchestration_service.get_voice_consistency_cache", no_cache
    )
    monkeypatch.setattr(
        "app.services.voice_consistency_orchestration_service.set_voice_consistency_cache",
        record_cache,
    )
    monkeypatch.setattr(
        "app.services.voice_consistency_orchestration_service.voice_current_sample_sufficient",
        lambda _samples, **_kwargs: True,
    )

    response = await client.post(
        f"/api/v1/intelligence/{book.id}/advisor/voice-consistency",
        headers=auth_headers,
        json={"text": submitted, "chapter_num": 4},
    )

    assert response.status_code == 200
    payload = response.json()
    assert set(payload["characters_reviewed"]) == {"Mara", "Lio"}
    assert payload["review"]["status"] == "complete"
    assert payload["coverage"]["processed_ranges"] == [{"start": 0, "end": len(submitted)}]
    assert payload["coverage"]["unattributed_ranges"] == []
    assert payload["coverage"]["unattributed_quoted_ranges"] == []
    assert len(payload["coverage"]["compared_ranges"]) == 2
    per_character = {
        item["character_name"]: item["processed_ranges"]
        for item in payload["coverage_by_character"]
    }
    assert per_character == {
        "Mara": [{"start": 0, "end": midpoint}],
        "Lio": [{"start": midpoint, "end": len(submitted)}],
    }
    assert len(cached_payloads) == 1

    async def read_recorded_cache(*_args, **_kwargs):
        return cached_payloads[0]

    monkeypatch.setattr(
        "app.services.voice_consistency_orchestration_service.get_voice_consistency_cache",
        read_recorded_cache,
    )
    cached_response = await client.post(
        f"/api/v1/intelligence/{book.id}/advisor/voice-consistency",
        headers=auth_headers,
        json={"text": submitted, "chapter_num": 4},
    )
    assert cached_response.status_code == 200
    assert cached_response.json()["cached"] is True
    assert len(cached_payloads) == 1

    malformed_cache = deepcopy(cached_payloads[0])
    malformed_cache["coverage"]["unattributed_ranges"] = [{"start": 0, "end": 1}]

    async def read_malformed_cache(*_args, **_kwargs):
        return malformed_cache

    monkeypatch.setattr(
        "app.services.voice_consistency_orchestration_service.get_voice_consistency_cache",
        read_malformed_cache,
    )
    refreshed_response = await client.post(
        f"/api/v1/intelligence/{book.id}/advisor/voice-consistency",
        headers=auth_headers,
        json={"text": submitted, "chapter_num": 4},
    )
    assert refreshed_response.status_code == 200
    assert refreshed_response.json()["cached"] is False
    assert refreshed_response.json()["review"]["status"] == "complete"
    assert len(cached_payloads) == 2

    leave_gap = True
    partial = await client.post(
        f"/api/v1/intelligence/{book.id}/advisor/voice-consistency",
        headers=auth_headers,
        json={"text": submitted, "chapter_num": 4},
    )
    assert partial.status_code == 200
    partial_payload = partial.json()
    assert partial_payload["review"]["status"] == "partial_evidence"
    assert partial_payload["coverage"]["unattributed_ranges"] == [
        {"start": len(submitted) - 10, "end": len(submitted)}
    ]
    assert "not a complete voice verdict" in partial_payload["review"]["overall_verdict"]
    assert len(cached_payloads) == 2

    leave_gap = False
    leave_quote_unattributed = True
    unassigned = await client.post(
        f"/api/v1/intelligence/{book.id}/advisor/voice-consistency",
        headers=auth_headers,
        json={"text": submitted, "chapter_num": 4},
    )
    assert unassigned.status_code == 200
    unassigned_payload = unassigned.json()
    assert unassigned_payload["coverage"]["unattributed_ranges"] == []
    assert unassigned_payload["review"]["status"] == "partial_evidence"
    assert unassigned_payload["coverage"]["unattributed_quoted_ranges"] == [
        {
            "start": submitted.index("I will search the north bank before morning arrives."),
            "end": submitted.index("I will search the north bank before morning arrives.")
            + len("I will search the north bank before morning arrives."),
        }
    ]
    assert (
        "quoted dialogue could not be assigned" in unassigned_payload["review"]["overall_verdict"]
    )
    assert len(cached_payloads) == 2


@pytest.mark.parametrize("baseline_confidence", ["unverified_narrator", "contextual"])
@pytest.mark.asyncio
async def test_first_person_review_reports_tentative_narrator_baseline_as_partial(
    client, db, auth_headers, monkeypatch, baseline_confidence
):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = uuid.UUID(me.json()["id"])
    book = Book(
        user_id=user_id,
        title="Changing viewpoints",
        format="manual",
        work_type="novel",
        s3_key="books/changing-viewpoints.txt",
        status="ready",
        mode="author",
    )
    db.add(book)
    await db.flush()
    narrator = Character(
        book_id=book.id,
        name="Mara",
        role="mc",
        first_chapter=1,
        mention_count=10,
        visibility_state="visible",
        approval_state="approved",
    )
    db.add(narrator)
    await db.commit()

    async def fake_context(*_args, **_kwargs):
        return "Story context"

    async def fake_baseline(*_args, **kwargs):
        assert kwargs["known_character_names"] == ["Mara"]
        return [
            {
                "chapter_number": chapter,
                "excerpt": (
                    "I crossed the old bridge before dawn. My coat held the rain while "
                    "the watch changed at the gate, and I waited for the lamps to brighten "
                    "before I returned to the square to find the missing letters. "
                )
                * 2,
                "attribution_confidence": baseline_confidence,
            }
            for chapter in (1, 2, 3)
        ]

    async def fake_completion(**_kwargs):
        assert not _kwargs["db"].in_transaction()
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason="stop",
                    message=SimpleNamespace(
                        content=json.dumps(
                            {
                                "overall_verdict": "The narrator seems inconsistent.",
                                "issues": [
                                    {
                                        "character_name": "Mara",
                                        "classification": "confirmed",
                                        "severity": "moderate",
                                        "title": "Register shift",
                                        "description": "The narration sounds less formal.",
                                        "submitted_excerpt": "I returned to the square",
                                        "baseline_excerpt": "I crossed the old bridge before dawn.",
                                        "baseline_chapter_number": 1,
                                        "confidence": 0.91,
                                        "revision_direction": "Compare the established phrasing.",
                                        "intentionality_prompt": "Is the change intentional?",
                                    }
                                ],
                            }
                        )
                    ),
                )
            ]
        )

    async def fake_get_cache(*_args, **_kwargs):
        return None

    async def fail_if_cached(*_args, **_kwargs):
        raise AssertionError("Tentative narrator review must not be cached as complete")

    monkeypatch.setattr(
        "app.services.voice_consistency_orchestration_service.build_story_context", fake_context
    )
    monkeypatch.setattr(
        "app.services.voice_consistency_orchestration_service.load_voice_baseline_samples",
        fake_baseline,
    )
    monkeypatch.setattr(
        "app.services.voice_consistency_orchestration_service.create_tracked_chat_completion",
        fake_completion,
    )
    monkeypatch.setattr(
        "app.services.voice_consistency_orchestration_service.get_openai_client", _FakeOpenAIClient
    )
    monkeypatch.setattr(
        "app.services.voice_consistency_orchestration_service.get_voice_consistency_cache",
        fake_get_cache,
    )
    monkeypatch.setattr(
        "app.services.voice_consistency_orchestration_service.set_voice_consistency_cache",
        fail_if_cached,
    )
    passage = (
        "I returned to the square after the storm and checked every lantern along "
        "the empty road. I wondered whether the letters had survived the rain and "
        "whether the watch captain would still be waiting near the gate when I arrived. "
        "I kept walking until the bells rang at the station behind me."
    )

    response = await client.post(
        f"/api/v1/intelligence/{book.id}/advisor/voice-consistency",
        headers=auth_headers,
        json={
            "text": passage,
            "chapter_num": 4,
            "character_id": str(narrator.id),
            "voice_mode": "first_person_narration",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["review"]["status"] == "partial_evidence"
    assert payload["review"]["issues"][0]["classification"] == "possible"
    assert payload["character_matches"] == []
    assert payload["baseline_evidence"][0]["baseline_attribution_confidence"] == (
        baseline_confidence
    )
    assert "tentative" in payload["review"]["overall_verdict"].lower()
    warning_fragment = (
        "direct address" if baseline_confidence == "contextual" else "do not independently identify"
    )
    assert any(warning_fragment in warning for warning in payload["warnings"])


@pytest.mark.asyncio
async def test_voice_review_reports_unavailable_manuscript_baseline_as_retryable(
    client, db, auth_headers, monkeypatch
):
    logged_failures = []

    def record_warning(message, *args):
        logged_failures.append((message % args, get_request_id()))

    monkeypatch.setattr("app.api.v1.routes.advisor.voice.logger.warning", record_warning)
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = uuid.UUID(me.json()["id"])
    book = Book(
        user_id=user_id,
        title="Baseline storage test",
        format="manual",
        work_type="novel",
        s3_key="books/baseline-storage.txt",
        status="ready",
        mode="author",
    )
    db.add(book)
    await db.flush()
    character = Character(book_id=book.id, name="Mara", role="mc", first_chapter=1, mention_count=3)
    db.add(character)
    await db.commit()

    async def fake_context(*_args, **_kwargs):
        return "Story context"

    async def unavailable_source(*_args, **_kwargs):
        raise VoiceBaselineSourceError("voice_baseline_source_unavailable")

    monkeypatch.setattr(
        "app.services.voice_consistency_orchestration_service.build_story_context", fake_context
    )
    monkeypatch.setattr(
        "app.services.voice_consistency_orchestration_service.load_voice_baseline_samples",
        unavailable_source,
    )

    response = await client.post(
        f"/api/v1/intelligence/{book.id}/advisor/voice-consistency",
        headers=auth_headers,
        json={
            "text": 'Mara said, "We should leave before dawn."',
            "chapter_num": 2,
            "character_id": str(character.id),
        },
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Something went wrong. Please try again."

    streamed = await client.post(
        f"/api/v1/intelligence/{book.id}/advisor/voice-consistency-stream",
        headers={**auth_headers, "X-Request-ID": "voice-storage-test"},
        json={
            "text": 'Mara said, "We should leave before dawn."',
            "chapter_num": 2,
            "character_id": str(character.id),
        },
    )
    assert streamed.status_code == 200
    assert "Stored manuscript text for the voice baseline could not be loaded" in streamed.text
    assert len(logged_failures) == 1
    assert "error_category=manuscript_source" in logged_failures[0][0]
    assert f"book_id={book.id}" in logged_failures[0][0]
    assert "Mara said" not in logged_failures[0][0]
    assert logged_failures[0][1] == "voice-storage-test"


@pytest.mark.asyncio
async def test_voice_consistency_endpoint_limits_review_to_selected_character(
    client, db, auth_headers, monkeypatch
):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert me.status_code == 200
    user_id = uuid.UUID(me.json()["id"])

    book = Book(
        user_id=user_id,
        title="Signal Fire",
        format="manual",
        work_type="novel",
        s3_key="books/signal-fire.txt",
        status="ready",
        mode="author",
    )
    db.add(book)
    await db.flush()

    iris = Character(
        book_id=book.id,
        name="Iris",
        role="mc",
        first_chapter=1,
        mention_count=24,
        trait_state={},
        personality_tags=["sharp"],
        motivations=["Protect the city"],
        analysis_metadata={
            "profile_claims": [
                {
                    "field": "personality_tags",
                    "value": "sharp",
                    "quote": "I will hold the line until sunrise",
                    "chapter_number": 1,
                }
            ]
        },
    )
    milo = Character(
        book_id=book.id,
        name="Milo",
        role="sc",
        first_chapter=1,
        mention_count=19,
        trait_state={},
        personality_tags=["steady"],
        motivations=["Keep Iris safe"],
    )
    db.add_all([iris, milo])
    await db.flush()
    db.add_all(
        [
            CharacterVoiceProfile(
                book_id=book.id,
                character_id=iris.id,
                sample_dialogue_count=6,
                sample_word_count=80,
            ),
            CharacterVoiceProfile(
                book_id=book.id,
                character_id=milo.id,
                sample_dialogue_count=5,
                sample_word_count=72,
            ),
        ]
    )
    await db.commit()
    submitted_text = (
        'Iris said, "I can handle this alone, but I need everyone to wait by the bridge '
        'until the rain stops tonight." '
        'Iris replied, "The lanterns should remain lit until the last traveler crosses safely."'
    )

    async def _fake_story_context(*_args, **_kwargs):
        return "Story context"

    loaded_baselines: list[str] = []
    long_baseline_tail = "The final signal is the copper compass by the river."

    async def _fake_baseline(*_args, **kwargs):
        loaded_baselines.append(kwargs["character_name"])
        return [
            {
                "chapter_number": 1 if index < 3 else 2,
                "excerpt": (
                    "I will hold the line until sunrise, even if the road is closed "
                    f"tonight, according to report {index}. "
                    + (
                        "I will keep watch until morning. " * 8 + long_baseline_tail
                        if index == 0
                        else ""
                    )
                ),
            }
            for index in range(5)
        ]

    async def _fake_chat_completion(**_kwargs):
        assert long_baseline_tail in _kwargs["messages"][1]["content"]
        assert "Story context" not in _kwargs["messages"][0]["content"]
        assert "Cited profile notes" in _kwargs["messages"][1]["content"]
        assert "personality_tags: sharp" in _kwargs["messages"][1]["content"]
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason="stop",
                    message=SimpleNamespace(
                        content=json.dumps(
                            {
                                "overall_verdict": "Iris stays on voice.",
                                "issues": [],
                            }
                        )
                    ),
                )
            ]
        )

    provider_client = _FakeOpenAIClient()
    monkeypatch.setattr(
        "app.services.voice_consistency_orchestration_service.get_openai_client",
        lambda: provider_client,
    )
    monkeypatch.setattr(
        "app.services.voice_consistency_orchestration_service.build_story_context",
        _fake_story_context,
    )
    monkeypatch.setattr(
        "app.services.voice_consistency_orchestration_service.load_voice_baseline_samples",
        _fake_baseline,
    )
    monkeypatch.setattr(
        "app.services.voice_consistency_orchestration_service.create_tracked_chat_completion",
        _fake_chat_completion,
    )

    def _fake_alternate_match(*, character_name, submitted_excerpts, own_score, baseline_by_name):
        assert character_name == "Iris"
        assert submitted_excerpts
        assert "Milo" in baseline_by_name
        assert own_score >= 0
        return "Milo", 86

    monkeypatch.setattr(
        "app.services.voice_consistency_orchestration_service.closest_alternate_voice_match",
        _fake_alternate_match,
    )

    cache_keys = []

    async def _fake_get_voice_consistency_cache(_book_id, cache_key, **_kwargs):
        cache_keys.append(cache_key)
        return None

    cached_payloads = []

    async def _fake_set_voice_consistency_cache(*_args, **_kwargs):
        cached_payloads.append(_args[2])
        return None

    monkeypatch.setattr(
        "app.services.voice_consistency_orchestration_service.get_voice_consistency_cache",
        _fake_get_voice_consistency_cache,
    )
    monkeypatch.setattr(
        "app.services.voice_consistency_orchestration_service.set_voice_consistency_cache",
        _fake_set_voice_consistency_cache,
    )

    response = await client.post(
        f"/api/v1/intelligence/{book.id}/advisor/voice-consistency",
        headers=auth_headers,
        json={
            "text": submitted_text,
            "chapter_num": 3,
            "character_id": str(iris.id),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["characters_reviewed"] == ["Iris"]
    assert [item["character_name"] for item in payload["character_matches"]] == ["Iris"]
    assert payload["review"]["status"] == "complete"
    assert loaded_baselines == ["Iris", "Milo"]
    assert payload["coverage"]["total_characters"] == len(submitted_text)
    assert payload["coverage_by_character"] == [{"character_name": "Iris", **payload["coverage"]}]
    assert payload["character_matches"][0]["closest_other_character"] == "Milo"
    assert payload["character_matches"][0]["closest_other_score"] == 86

    iris.motivations = ["Leave the city before sunrise"]
    await db.commit()
    second = await client.post(
        f"/api/v1/intelligence/{book.id}/advisor/voice-consistency",
        headers=auth_headers,
        json={
            "text": submitted_text,
            "chapter_num": 3,
            "character_id": str(iris.id),
        },
    )
    assert second.status_code == 200
    assert len(cache_keys) == 2
    assert cache_keys[0] != cache_keys[1]

    contextual = await client.post(
        f"/api/v1/intelligence/{book.id}/advisor/voice-consistency",
        headers=auth_headers,
        json={
            "text": (
                'Iris closed the window. She said, "I can handle this alone, but I need '
                'everyone to wait by the bridge until the rain stops tonight."'
            ),
            "chapter_num": 3,
            "character_id": str(iris.id),
        },
    )
    assert contextual.status_code == 200
    contextual_payload = contextual.json()
    assert contextual_payload["review"]["status"] == "partial_evidence"
    assert contextual_payload["baseline_evidence"][0]["attribution_confidence"] == "contextual"
    assert "tentative" in contextual_payload["review"]["overall_verdict"].lower()
    assert contextual_payload["character_matches"] == []
    assert any("No numeric voice match" in warning for warning in contextual_payload["warnings"])
    assert len(cached_payloads) == 2

    async def _disconnected_provider(**_kwargs):
        raise APIConnectionError(
            request=Request("POST", "https://api.openai.com/v1/chat/completions")
        )

    async def _no_retry_delay(_seconds):
        return None

    monkeypatch.setattr(
        "app.services.voice_consistency_orchestration_service.create_tracked_chat_completion",
        _disconnected_provider,
    )
    monkeypatch.setattr(
        "app.services.voice_consistency_review_service.asyncio.sleep", _no_retry_delay
    )
    unavailable = await client.post(
        f"/api/v1/intelligence/{book.id}/advisor/voice-consistency",
        headers=auth_headers,
        json={
            "text": submitted_text,
            "chapter_num": 3,
            "character_id": str(iris.id),
        },
    )
    assert unavailable.status_code == 503
    # The global HTTP handler intentionally masks 5xx details on direct calls;
    # the streaming endpoint renders the allowlisted retry guidance.
    assert unavailable.json()["detail"] == "Something went wrong. Please try again."
    streamed_unavailable = await client.post(
        f"/api/v1/intelligence/{book.id}/advisor/voice-consistency-stream",
        headers=auth_headers,
        json={
            "text": submitted_text,
            "chapter_num": 3,
            "character_id": str(iris.id),
        },
    )
    assert streamed_unavailable.status_code == 200
    assert "event: error" in streamed_unavailable.text
    assert "temporarily unavailable" in streamed_unavailable.text
    assert "event: done" not in streamed_unavailable.text

    async def _busy_provider(**_kwargs):
        request = Request("POST", "https://api.openai.com/v1/chat/completions")
        raise APIStatusError("provider busy", response=Response(503, request=request), body=None)

    monkeypatch.setattr(
        "app.services.voice_consistency_orchestration_service.create_tracked_chat_completion",
        _busy_provider,
    )
    busy = await client.post(
        f"/api/v1/intelligence/{book.id}/advisor/voice-consistency",
        headers=auth_headers,
        json={"text": submitted_text, "chapter_num": 3, "character_id": str(iris.id)},
    )
    assert busy.status_code == 503

    async def _timed_out_provider(**_kwargs):
        raise TimeoutError("voice provider timed out")

    monkeypatch.setattr(
        "app.services.voice_consistency_orchestration_service.create_tracked_chat_completion",
        _timed_out_provider,
    )
    timed_out = await client.post(
        f"/api/v1/intelligence/{book.id}/advisor/voice-consistency",
        headers=auth_headers,
        json={"text": submitted_text, "chapter_num": 3, "character_id": str(iris.id)},
    )
    assert timed_out.status_code == 503

    truncated_calls = 0

    async def _truncated_provider(**_kwargs):
        nonlocal truncated_calls
        truncated_calls += 1
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason="length",
                    message=SimpleNamespace(
                        content='{"issues":[],"overall_verdict":"No supported shift."}'
                    ),
                )
            ]
        )

    monkeypatch.setattr(
        "app.services.voice_consistency_orchestration_service.create_tracked_chat_completion",
        _truncated_provider,
    )
    truncated = await client.post(
        f"/api/v1/intelligence/{book.id}/advisor/voice-consistency",
        headers=auth_headers,
        json={"text": submitted_text, "chapter_num": 3, "character_id": str(iris.id)},
    )
    assert truncated.status_code == 503
    assert truncated_calls == 2
    assert provider_client.close_calls == 0


@pytest.mark.asyncio
async def test_voice_review_short_current_line_is_tentative_and_has_no_match_score(
    client, db, auth_headers, monkeypatch
):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    book = Book(
        user_id=uuid.UUID(me.json()["id"]),
        title="Bridge signals",
        format="manual",
        work_type="novel",
        s3_key="books/bridge-signals.txt",
        status="ready",
        mode="author",
    )
    db.add(book)
    await db.flush()
    character = Character(book_id=book.id, name="Mara", first_chapter=1, mention_count=5)
    db.add(character)
    await db.commit()

    baseline = [
        {
            "chapter_number": chapter,
            "excerpt": (
                "I shall remain beside the bridge until the evening lamps are lit, "
                "and I will wait for every traveler to return safely."
            ),
        }
        for chapter in (1, 2, 3)
    ]

    async def fake_baseline(*_args, **_kwargs):
        return baseline

    async def fake_context(*_args, **_kwargs):
        return "A bridge crossing."

    async def fake_model(**_kwargs):
        issue = {
            "character_name": "Mara",
            "classification": "confirmed",
            "severity": "moderate",
            "title": "Abrupt register",
            "description": "The command is shorter than Mara's earlier speech.",
            "submitted_excerpt": "Wait.",
            "baseline_excerpt": baseline[0]["excerpt"],
            "baseline_chapter_number": 1,
            "confidence": 0.96,
            "revision_direction": "Check whether urgency explains the shorter command.",
            "intentionality_prompt": "Is this a deliberate change under pressure?",
        }
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason="stop",
                    message=SimpleNamespace(
                        content=json.dumps(
                            {
                                "overall_verdict": "Mara's voice is inconsistent.",
                                "issues": [issue],
                            }
                        )
                    ),
                )
            ]
        )

    async def no_cache(*_args, **_kwargs):
        return None

    async def unexpected_cache_write(*_args, **_kwargs):
        pytest.fail("A tentative voice review must not be cached as complete")

    monkeypatch.setattr(
        "app.services.voice_consistency_orchestration_service.build_story_context", fake_context
    )
    monkeypatch.setattr(
        "app.services.voice_consistency_orchestration_service.load_voice_baseline_samples",
        fake_baseline,
    )
    monkeypatch.setattr(
        "app.services.voice_consistency_orchestration_service.get_openai_client",
        lambda: _FakeOpenAIClient(),
    )
    monkeypatch.setattr(
        "app.services.voice_consistency_orchestration_service.create_tracked_chat_completion",
        fake_model,
    )
    monkeypatch.setattr(
        "app.services.voice_consistency_orchestration_service.get_voice_consistency_cache", no_cache
    )
    monkeypatch.setattr(
        "app.services.voice_consistency_orchestration_service.set_voice_consistency_cache",
        unexpected_cache_write,
    )

    response = await client.post(
        f"/api/v1/intelligence/{book.id}/advisor/voice-consistency",
        headers=auth_headers,
        json={
            "text": 'Mara said, "Wait."',
            "chapter_num": 4,
            "character_id": str(character.id),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["review"]["status"] == "partial_evidence"
    assert payload["character_matches"] == []
    assert payload["review"]["issues"][0]["classification"] == "possible"
    assert payload["review"]["issues"][0]["confidence"] == 0.75
    assert "too limited" in payload["review"]["overall_verdict"]
    assert any("reliable voice match" in warning for warning in payload["warnings"])


@pytest.mark.asyncio
async def test_voice_consistency_endpoint_does_not_score_unattributed_dialogue(
    client, db, auth_headers, monkeypatch
):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert me.status_code == 200
    user_id = uuid.UUID(me.json()["id"])

    book = Book(
        user_id=user_id,
        title="Signal Fire",
        format="manual",
        work_type="novel",
        s3_key="books/signal-fire.txt",
        status="ready",
        mode="author",
    )
    db.add(book)
    await db.flush()

    iris = Character(
        book_id=book.id,
        name="Iris",
        role="mc",
        first_chapter=1,
        mention_count=24,
        trait_state={},
        personality_tags=["sharp"],
        motivations=["Protect the city"],
    )
    milo = Character(
        book_id=book.id,
        name="Milo",
        role="sc",
        first_chapter=1,
        mention_count=19,
        trait_state={},
        personality_tags=["steady"],
        motivations=["Keep Iris safe"],
    )
    db.add_all([iris, milo])
    await db.flush()
    db.add_all(
        [
            CharacterVoiceProfile(
                book_id=book.id,
                character_id=iris.id,
                sample_dialogue_count=6,
                sample_word_count=80,
            ),
            CharacterVoiceProfile(
                book_id=book.id,
                character_id=milo.id,
                sample_dialogue_count=5,
                sample_word_count=72,
            ),
        ]
    )
    await db.commit()

    async def _fake_story_context(*_args, **_kwargs):
        return "Story context"

    async def _fake_baseline(*_args, **_kwargs):
        return [
            {
                "chapter_number": chapter,
                "excerpt": "I will hold the line until sunrise, even if the road is closed tonight.",
            }
            for chapter in (1, 2, 4, 5, 6)
        ]

    monkeypatch.setattr(
        "app.services.voice_consistency_orchestration_service.build_story_context",
        _fake_story_context,
    )
    monkeypatch.setattr(
        "app.services.voice_consistency_orchestration_service.load_voice_baseline_samples",
        _fake_baseline,
    )

    response = await client.post(
        f"/api/v1/intelligence/{book.id}/advisor/voice-consistency",
        headers=auth_headers,
        json={
            "text": "Iris says hello.",
            "chapter_num": 3,
            "character_id": str(iris.id),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["review"]["status"] == "insufficient_evidence"
    assert payload["characters_reviewed"] == []
    assert payload["character_matches"] == []
    assert any("could be confidently identified" in warning for warning in payload["warnings"])


@pytest.mark.asyncio
async def test_voice_finding_decision_endpoint_persists_and_updates_author_choice(
    client, db, auth_headers
):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert me.status_code == 200
    user_id = uuid.UUID(me.json()["id"])
    book = Book(
        user_id=user_id,
        title="Voice decisions",
        format="manual",
        work_type="novel",
        s3_key="books/voice-decisions.txt",
        status="ready",
        mode="author",
    )
    db.add(book)
    await db.commit()
    finding_key = "e" * 64
    url = f"/api/v1/intelligence/{book.id}/advisor/voice-decisions/{finding_key}"

    first = await client.put(
        url,
        headers=auth_headers,
        json={"decision": "intentional", "note": "She is under pressure."},
    )
    second = await client.put(
        url,
        headers=auth_headers,
        json={"decision": "resolved", "note": None},
    )

    assert first.status_code == 200
    assert first.json()["decision"] == "intentional"
    assert second.status_code == 200
    rows = (
        (
            await db.execute(
                select(VoiceReviewDecision).where(
                    VoiceReviewDecision.book_id == book.id,
                    VoiceReviewDecision.user_id == user_id,
                    VoiceReviewDecision.finding_key == finding_key,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].decision == "resolved"

    invalid = await client.put(
        f"/api/v1/intelligence/{book.id}/advisor/voice-decisions/not-a-hash",
        headers=auth_headers,
        json={"decision": "intentional"},
    )
    assert invalid.status_code == 422

    stranger = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"stranger-{uuid.uuid4().hex[:8]}@lorevia.app",
            "username": f"stranger{uuid.uuid4().hex[:8]}",
            "password": "SecurePass456!@#",
            "accepted_terms": True,
            "device_id": f"device-{uuid.uuid4().hex}",
        },
    )
    assert stranger.status_code == 201
    stranger_headers = {"Authorization": f"Bearer {create_access_token(stranger.json()['id'])}"}
    forbidden = await client.put(url, headers=stranger_headers, json={"decision": "incorrect"})
    assert forbidden.status_code in {403, 404}
