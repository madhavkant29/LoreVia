from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from app.models.user import LlmUsageEvent, User
from app.utils import llm_usage_utils
from app.utils.llm_usage_utils import create_tracked_chat_completion, summarize_llm_usage_for_user


@pytest.mark.asyncio
async def test_summarize_llm_usage_for_user_returns_totals(db):
    user = User(email="llm-usage@lorevia.app", username="llmusage", password_hash="hash", tier="author")
    db.add(user)
    await db.flush()

    db.add_all(
        [
            LlmUsageEvent(
                user_id=user.id,
                provider="openai",
                model="gpt-4o-mini",
                operation="chat_completion",
                feature="advisor_message",
                prompt_tokens=120,
                completion_tokens=30,
                total_tokens=150,
            ),
            LlmUsageEvent(
                user_id=user.id,
                provider="openai",
                model="text-embedding-3-small",
                operation="embedding",
                feature="semantic_search_query",
                prompt_tokens=60,
                completion_tokens=0,
                total_tokens=60,
            ),
        ]
    )
    await db.commit()

    summary = await summarize_llm_usage_for_user(db, user.id)

    assert summary.request_count == 2
    assert summary.prompt_tokens == 180
    assert summary.completion_tokens == 30
    assert summary.total_tokens == 210


@pytest.mark.asyncio
async def test_summarize_llm_usage_for_user_handles_unknown_user(db):
    summary = await summarize_llm_usage_for_user(db, uuid.uuid4())

    assert summary.request_count == 0
    assert summary.prompt_tokens == 0
    assert summary.completion_tokens == 0
    assert summary.total_tokens == 0


@pytest.mark.asyncio
async def test_create_tracked_chat_completion_returns_response_when_usage_recording_fails(monkeypatch):
    response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))])
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace()))

    async def _fake_create(**_kwargs):
        return response

    async def _fail_record(**_kwargs):
        raise TimeoutError("usage table unavailable")

    client.chat.completions.create = _fake_create
    monkeypatch.setattr(llm_usage_utils, "record_llm_usage_event", _fail_record)

    result = await create_tracked_chat_completion(
        client=client,
        feature="character_relationship_extraction",
        model="gpt-test",
        user_id=uuid.uuid4(),
        messages=[],
    )

    assert result is response
