from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.models.user import LlmUsageEvent, User
from app.utils import llm_usage_utils
from app.utils.llm_usage_utils import (
    assert_manual_reprocess_token_capacity,
    create_tracked_chat_completion,
    create_tracked_embedding,
    llm_token_caps_for_user,
    manual_reprocess_token_caps_for_user,
    summarize_llm_usage_for_user,
)


@pytest.mark.asyncio
async def test_summarize_llm_usage_for_user_returns_totals(db):
    user = User(
        email="llm-usage@lorevia.app", username="llmusage", password_hash="hash", tier="author"
    )
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
async def test_create_tracked_chat_completion_returns_response_when_usage_recording_fails(
    db, monkeypatch
):
    user = User(
        email="tracked-recording@lorevia.app",
        username="trackedrecording",
        password_hash="hash",
        tier="author",
    )
    db.add(user)
    await db.commit()
    response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))])
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace()))

    async def _fake_create(**_kwargs):
        return response

    async def _reserve(**kwargs):
        return SimpleNamespace(id="tracked-reservation", operation="chat", user_id=kwargs["user_id"])

    async def _finish(*_args, **_kwargs):
        return None

    client.chat.completions.create = _fake_create
    monkeypatch.setattr("app.services.llm_control_service.reserve_llm_call", _reserve)
    monkeypatch.setattr("app.services.llm_control_service.finish_llm_reservation", _finish)

    result = await create_tracked_chat_completion(
        client=client,
        feature="character_relationship_extraction",
        model="gpt-test",
        db=db,
        user_id=user.id,
        messages=[],
    )

    assert result is response


def test_llm_token_caps_select_tier_limits(monkeypatch):
    monkeypatch.setattr(llm_usage_utils.settings, "FREE_LLM_TOKENS_5H", 25, raising=False)
    monkeypatch.setattr(llm_usage_utils.settings, "AUTHOR_LLM_TOKENS_5H", 150, raising=False)
    monkeypatch.setattr(llm_usage_utils.settings, "ARCHITECT_LLM_TOKENS_5H", 500, raising=False)

    free_caps = llm_token_caps_for_user(
        SimpleNamespace(tier="free", created_at=datetime(2020, 1, 1, tzinfo=UTC))
    )
    author_caps = llm_token_caps_for_user(
        SimpleNamespace(tier="author", created_at=datetime(2020, 1, 1, tzinfo=UTC))
    )
    architect_caps = llm_token_caps_for_user(
        SimpleNamespace(tier="architect", created_at=datetime(2020, 1, 1, tzinfo=UTC))
    )

    assert free_caps.five_hour == 25
    assert author_caps.five_hour == 150
    assert architect_caps.five_hour == 500


def test_llm_token_caps_treat_trial_as_author(monkeypatch):
    now = datetime.now(UTC)
    monkeypatch.setattr(llm_usage_utils.settings, "AUTHOR_LLM_TOKENS_WEEK", 700, raising=False)

    caps = llm_token_caps_for_user(SimpleNamespace(tier="free", created_at=now - timedelta(days=2)))

    assert caps.weekly == 700
    assert (
        manual_reprocess_token_caps_for_user(
            SimpleNamespace(tier="free", created_at=now - timedelta(days=2))
        ).weekly
        == 700
    )


@pytest.mark.parametrize(
    ("cap_attr", "event_age", "window_label"),
    [
        ("FREE_LLM_TOKENS_5H", timedelta(hours=1), "5-hour"),
        ("FREE_LLM_TOKENS_WEEK", timedelta(days=2), "weekly"),
        ("FREE_LLM_TOKENS_MONTH", timedelta(days=10), "monthly"),
    ],
)
@pytest.mark.asyncio
async def test_manual_reprocess_token_capacity_blocks_window_overage(
    db,
    monkeypatch,
    cap_attr,
    event_age,
    window_label,
):
    unique_suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"manual-token-{unique_suffix}@lorevia.app",
        username=f"manualtoken{unique_suffix}",
        password_hash="hash",
        tier="free",
    )
    db.add(user)
    await db.flush()
    now = datetime.now(UTC)
    user.created_at = now - timedelta(days=60)
    db.add(
        LlmUsageEvent(
            user_id=user.id,
            provider="openai",
            model="gpt-test",
            operation="chat_completion",
            feature="manual_reprocess",
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=24,
            created_at=now - event_age,
        )
    )
    await db.commit()
    monkeypatch.setattr(llm_usage_utils.settings, cap_attr, 25, raising=False)

    with pytest.raises(HTTPException) as exc:
        await assert_manual_reprocess_token_capacity(db, user, estimated_tokens=2, now=now)

    assert exc.value.status_code == 429
    assert window_label in str(exc.value.detail)


@pytest.mark.asyncio
async def test_tracked_chat_completion_blocks_before_openai_call_when_token_cap_exceeded(
    db, monkeypatch
):
    user = User(
        email="tracked-block@lorevia.app",
        username="trackedblock",
        password_hash="hash",
        tier="free",
    )
    db.add(user)
    await db.flush()
    user.created_at = datetime.now(UTC) - timedelta(days=60)
    db.add(
        LlmUsageEvent(
            user_id=user.id,
            provider="openai",
            model="gpt-test",
            operation="chat_completion",
            feature="advisor_message",
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=24,
            created_at=datetime.now(UTC) - timedelta(hours=1),
        )
    )
    await db.commit()
    monkeypatch.setattr(llm_usage_utils.settings, "FREE_LLM_TOKENS_5H", 25, raising=False)
    called = False
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace()))

    async def _fake_create(**_kwargs):
        nonlocal called
        called = True
        return SimpleNamespace()

    client.chat.completions.create = _fake_create

    async def _blocked(**_kwargs):
        raise HTTPException(429, "5-hour LLM token allowance reached")

    monkeypatch.setattr("app.services.llm_control_service.reserve_llm_call", _blocked)

    with pytest.raises(HTTPException) as exc:
        await create_tracked_chat_completion(
            client=client,
            feature="advisor_message",
            model="gpt-test",
            db=db,
            user_id=user.id,
            messages=[{"role": "user", "content": "Spend tokens"}],
            max_tokens=2,
        )

    assert exc.value.status_code == 429
    assert called is False


@pytest.mark.asyncio
async def test_tracked_embedding_blocks_before_openai_call_when_token_cap_exceeded(db, monkeypatch):
    user = User(
        email="embed-block@lorevia.app", username="embedblock", password_hash="hash", tier="free"
    )
    db.add(user)
    await db.flush()
    user.created_at = datetime.now(UTC) - timedelta(days=60)
    db.add(
        LlmUsageEvent(
            user_id=user.id,
            provider="openai",
            model="text-embedding-3-small",
            operation="embedding",
            feature="chapter_chunk_embedding",
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=24,
            created_at=datetime.now(UTC) - timedelta(hours=1),
        )
    )
    await db.commit()
    monkeypatch.setattr(llm_usage_utils.settings, "FREE_LLM_TOKENS_5H", 25, raising=False)
    called = False
    client = SimpleNamespace(embeddings=SimpleNamespace())

    async def _fake_create(**_kwargs):
        nonlocal called
        called = True
        return SimpleNamespace()

    client.embeddings.create = _fake_create

    async def _blocked(**_kwargs):
        raise HTTPException(429, "5-hour LLM token allowance reached")

    monkeypatch.setattr("app.services.llm_control_service.reserve_llm_call", _blocked)

    with pytest.raises(HTTPException) as exc:
        await create_tracked_embedding(
            client=client,
            feature="chapter_chunk_embedding",
            model="text-embedding-3-small",
            db=db,
            user_id=user.id,
            input="Spend tokens",
        )

    assert exc.value.status_code == 429
    assert called is False
