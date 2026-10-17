import json
import uuid
from types import SimpleNamespace

import pytest

from app.models.book import Book
from app.models.character import Character, CharacterVoiceProfile


class _FakeOpenAIClient:
    async def close(self):
        return None


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

    async def _fake_semantic_search(*_args, **_kwargs):
        return []

    async def _fake_story_context(*_args, **_kwargs):
        return "Story context"

    async def _fake_chat_completion(**_kwargs):
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=json.dumps(
                            {
                                "overall_verdict": "Iris stays on voice.",
                                "issues": [],
                            }
                        )
                    )
                )
            ]
        )

    monkeypatch.setattr(
        "app.api.v1.routes.advisor.voice.get_openai_client", lambda: _FakeOpenAIClient()
    )
    monkeypatch.setattr("app.api.v1.routes.advisor.voice.semantic_search", _fake_semantic_search)
    monkeypatch.setattr("app.api.v1.routes.advisor.voice.build_story_context", _fake_story_context)
    monkeypatch.setattr(
        "app.api.v1.routes.advisor.voice.create_tracked_chat_completion", _fake_chat_completion
    )
    monkeypatch.setattr(
        "app.api.v1.routes.advisor.voice.extract_dialogue_samples_by_character",
        lambda *_args: {"Iris": ["I can handle this."]},
    )
    monkeypatch.setattr(
        "app.api.v1.routes.advisor.voice.compute_voice_metrics",
        lambda samples: {"sample_dialogue_count": len(samples)},
    )
    monkeypatch.setattr(
        "app.api.v1.routes.advisor.voice.score_voice_match",
        lambda _profile, metrics: (83 if metrics["sample_dialogue_count"] else 0, ["cadence"]),
    )
    monkeypatch.setattr(
        "app.api.v1.routes.advisor.voice.get_voice_consistency_cache",
        lambda *_args, **_kwargs: None,
    )

    async def _fake_get_voice_consistency_cache(*_args, **_kwargs):
        pass

    monkeypatch.setattr(
        "app.api.v1.routes.advisor.voice.get_voice_consistency_cache",
        _fake_get_voice_consistency_cache,
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
    assert payload["characters_reviewed"] == ["Iris"]
    assert [item["character_name"] for item in payload["character_matches"]] == ["Iris"]


@pytest.mark.asyncio
async def test_voice_consistency_endpoint_warns_on_selected_character_fallback(
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

    async def _fake_semantic_search(*_args, **_kwargs):
        return []

    async def _fake_story_context(*_args, **_kwargs):
        return "Story context"

    async def _fake_chat_completion(**_kwargs):
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=json.dumps(
                            {
                                "overall_verdict": "Iris still reads coherently.",
                                "issues": [],
                            }
                        )
                    )
                )
            ]
        )

    monkeypatch.setattr(
        "app.api.v1.routes.advisor.voice.get_openai_client", lambda: _FakeOpenAIClient()
    )
    monkeypatch.setattr("app.api.v1.routes.advisor.voice.semantic_search", _fake_semantic_search)
    monkeypatch.setattr("app.api.v1.routes.advisor.voice.build_story_context", _fake_story_context)
    monkeypatch.setattr(
        "app.api.v1.routes.advisor.voice.create_tracked_chat_completion", _fake_chat_completion
    )
    monkeypatch.setattr(
        "app.api.v1.routes.advisor.voice.extract_dialogue_samples_by_character",
        lambda *_args: {},
    )
    monkeypatch.setattr(
        "app.api.v1.routes.advisor.voice.compute_voice_metrics",
        lambda samples: {"sample_dialogue_count": len(samples)},
    )
    monkeypatch.setattr(
        "app.api.v1.routes.advisor.voice.score_voice_match",
        lambda _profile, metrics: (76 if metrics["sample_dialogue_count"] else 0, ["cadence"]),
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
    assert payload["characters_reviewed"] == ["Iris"]
    assert payload["warnings"] == [
        "Dialogue could not be confidently attributed to Iris; the review used the full submitted passage instead."
    ]
    assert payload["character_matches"][0]["sample_dialogue_count"] == 1
