import uuid

import pytest

from app.engine.intelligence.character_chat import chat_as_character
from app.models.character import Character


@pytest.mark.asyncio
async def test_character_chat_handles_missing_relationship_summaries(monkeypatch):
    captured: dict[str, object] = {}

    async def fake_complete_with_fallback(**kwargs):
        captured.update(kwargs)
        return "Life means what we choose to make of it."

    monkeypatch.setattr(
        "app.engine.intelligence.character_chat.complete_with_fallback",
        fake_complete_with_fallback,
    )

    character = Character(
        id=uuid.uuid4(),
        book_id=uuid.uuid4(),
        name="Aoi",
        first_chapter=1,
        personality_tags=["reflective"],
        motivations=["protecting her friends"],
        fears=["being left behind"],
        arc_summary="She is learning to trust herself.",
        trait_state={},
        growth_events=[],
    )

    reply = await chat_as_character(
        character=character,
        book_title="Sky Lanterns",
        current_chapter=8,
        context_summary="Aoi just survived a dangerous test.",
        search_context="She promised she would keep moving forward.",
        messages=[{"role": "user", "content": "What do you believe to be life's meaning?"}],
    )

    assert reply == "Life means what we choose to make of it."
    assert "no relationship evidence extracted yet" in str(captured["system"])


@pytest.mark.asyncio
async def test_character_chat_returns_fallback_for_blank_model_reply(monkeypatch):
    async def fake_complete_with_fallback(**kwargs):
        return "   "

    monkeypatch.setattr(
        "app.engine.intelligence.character_chat.complete_with_fallback",
        fake_complete_with_fallback,
    )

    character = Character(
        id=uuid.uuid4(),
        book_id=uuid.uuid4(),
        name="Aoi",
        first_chapter=1,
        trait_state={},
    )

    reply = await chat_as_character(
        character=character,
        book_title="Sky Lanterns",
        current_chapter=8,
        context_summary="",
        search_context="",
        messages=[{"role": "user", "content": "Hello?"}],
    )

    assert reply == "I don't know how to answer that just yet."
