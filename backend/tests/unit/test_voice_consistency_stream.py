import asyncio
import uuid

import pytest
from fastapi import HTTPException

from app.api.v1.routes.advisor import voice
from app.schemas.advisor import VoiceConsistencyRequest


@pytest.mark.asyncio
async def test_voice_stream_emits_heartbeats_then_complete_payload(monkeypatch):
    async def slow_review(**_kwargs):
        await asyncio.sleep(0.02)
        return {"review": {"status": "complete", "issues": []}}

    monkeypatch.setattr(voice, "voice_consistency_review", slow_review)
    monkeypatch.setattr(voice, "VOICE_STREAM_HEARTBEAT_SECONDS", 0.001)
    response = await voice.voice_consistency_review_stream(
        uuid.uuid4(),
        VoiceConsistencyRequest(text="Mara said hello."),
        db=object(),
        current_user=object(),
        _=object(),
    )
    events = [event async for event in response.body_iterator]

    assert "event: stage" in events[0]
    assert any("Still reviewing the full passage" in event for event in events)
    assert "event: done" in events[-1]
    assert '"status": "complete"' in events[-1]


@pytest.mark.asyncio
async def test_voice_stream_reports_review_error_instead_of_empty_success(monkeypatch):
    async def failed_review(**_kwargs):
        raise HTTPException(503, detail="Voice review temporarily unavailable.")

    monkeypatch.setattr(voice, "voice_consistency_review", failed_review)
    response = await voice.voice_consistency_review_stream(
        uuid.uuid4(),
        VoiceConsistencyRequest(text="Mara said hello."),
        db=object(),
        current_user=object(),
        _=object(),
    )
    events = [event async for event in response.body_iterator]

    assert any("event: error" in event for event in events)
    assert not any("event: done" in event for event in events)


@pytest.mark.asyncio
async def test_voice_stream_reports_retryable_provider_connection_error(monkeypatch):
    async def failed_review(**_kwargs):
        raise HTTPException(
            503,
            detail={
                "kind": "llm_provider",
                "message": "The AI service connection was interrupted. Your passage is unchanged; retry shortly.",
            },
        )

    monkeypatch.setattr(voice, "voice_consistency_review", failed_review)
    response = await voice.voice_consistency_review_stream(
        uuid.uuid4(),
        VoiceConsistencyRequest(text="Mara said hello."),
        db=object(),
        current_user=object(),
        _=object(),
    )
    events = [event async for event in response.body_iterator]

    assert any("AI service connection was interrupted" in event for event in events)
    assert not any("event: done" in event for event in events)


@pytest.mark.asyncio
async def test_voice_stream_cancels_review_when_client_disconnects(monkeypatch):
    cancelled = asyncio.Event()

    async def waiting_review(**_kwargs):
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    monkeypatch.setattr(voice, "voice_consistency_review", waiting_review)
    monkeypatch.setattr(voice, "VOICE_STREAM_HEARTBEAT_SECONDS", 0.001)
    response = await voice.voice_consistency_review_stream(
        uuid.uuid4(),
        VoiceConsistencyRequest(text="Mara said hello."),
        db=object(),
        current_user=object(),
        _=object(),
    )
    stream = response.body_iterator
    await anext(stream)
    await anext(stream)
    await stream.aclose()

    assert cancelled.is_set()
