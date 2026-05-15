from __future__ import annotations

import uuid

import pytest

from app.models.user import LlmUsageEvent, User
from app.utils.llm_usage_utils import summarize_llm_usage_for_user


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
