from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from httpx import Request
from openai import APIConnectionError
from sqlalchemy.exc import SQLAlchemyError

from app.models.user import LlmUsageEvent, User
from app.utils import llm_usage_utils
from app.utils.llm_usage_utils import (
    LLMIncompleteResponseError,
    assert_manual_reprocess_token_capacity,
    create_tracked_chat_completion,
    create_tracked_embedding,
    llm_token_caps_for_user,
    manual_reprocess_token_caps_for_user,
    require_complete_llm_response,
    summarize_llm_usage_for_user,
)


def test_structured_response_requires_an_explicit_provider_stop_reason():
    require_complete_llm_response(SimpleNamespace(choices=[SimpleNamespace(finish_reason="stop")]))
    for response in (
        SimpleNamespace(choices=[]),
        SimpleNamespace(choices=[SimpleNamespace(finish_reason="length")]),
        SimpleNamespace(choices=[SimpleNamespace(finish_reason="content_filter")]),
        SimpleNamespace(choices=[SimpleNamespace()]),
    ):
        with pytest.raises(LLMIncompleteResponseError, match="llm_response_incomplete"):
            require_complete_llm_response(response)
    with pytest.raises(LLMIncompleteResponseError) as exc_info:
        require_complete_llm_response(
            SimpleNamespace(choices=[SimpleNamespace(finish_reason="length")])
        )
    assert exc_info.value.finish_reason == "length"


@pytest.fixture(autouse=True)
def _use_offline_token_counter(monkeypatch):
    monkeypatch.setattr(
        llm_usage_utils,
        "count_tokens",
        lambda value: max(len(str(value or "").split()), 1),
    )


def test_llm_call_error_classification_retries_only_provider_failures():
    connection_error = APIConnectionError(
        request=Request("POST", "https://api.openai.com/v1/chat/completions")
    )
    capacity_error = HTTPException(429, "LLM capacity is temporarily busy. Retry shortly.")
    usage_error = HTTPException(429, "LLM usage token limit exceeded for the 5-hour window.")

    assert llm_usage_utils.is_llm_call_error(connection_error)
    assert llm_usage_utils.is_retryable_llm_call_error(connection_error)
    assert llm_usage_utils.is_llm_call_error(capacity_error)
    assert not llm_usage_utils.is_retryable_llm_call_error(capacity_error)
    assert llm_usage_utils.is_llm_call_error(usage_error)
    assert not llm_usage_utils.is_retryable_llm_call_error(usage_error)
    assert not llm_usage_utils.is_llm_call_error(ValueError("parse failure"))


def test_short_llm_coordination_retry_delay_rejects_budget_and_long_backoffs():
    retry_delay = llm_usage_utils.short_llm_coordination_retry_delay

    assert retry_delay(HTTPException(429, "LLM capacity busy", headers={"Retry-After": "5"})) == 5
    assert (
        retry_delay(
            HTTPException(503, "LLM coordination unavailable", headers={"Retry-After": "2"})
        )
        == 2
    )
    assert retry_delay(HTTPException(429, "LLM rate busy", headers={"Retry-After": "60"})) is None
    assert (
        retry_delay(HTTPException(429, {"kind": "llm_budget"}, headers={"Retry-After": "5"}))
        is None
    )
    assert (
        retry_delay(HTTPException(503, "LLM capacity busy", headers={"Retry-After": "nan"})) is None
    )
    assert retry_delay(HTTPException(429, "LLM capacity busy")) is None


def test_public_llm_http_error_message_keeps_allowance_message():
    exc = HTTPException(
        429,
        {
            "kind": "llm_budget",
            "message": "Monthly AI capacity has been reached.",
            "next_resume_at": "2026-09-01T00:00:00+00:00",
        },
    )

    assert (
        llm_usage_utils.public_llm_http_error_message(exc)
        == "Monthly AI capacity has been reached."
    )


def test_public_llm_http_error_message_keeps_safe_provider_retry_message():
    exc = HTTPException(
        503,
        {
            "kind": "llm_provider",
            "message": "The AI service connection was interrupted. Your passage is unchanged; retry shortly.",
        },
    )

    assert "retry shortly" in llm_usage_utils.public_llm_http_error_message(exc)


def test_public_llm_http_error_message_keeps_safe_manuscript_source_retry_message():
    exc = HTTPException(
        503,
        {
            "kind": "manuscript_source",
            "message": "Stored manuscript text is temporarily unavailable. Please retry.",
        },
    )

    assert "manuscript text" in llm_usage_utils.public_llm_http_error_message(exc)


@pytest.mark.asyncio
async def test_customer_scoped_call_without_user_fails_before_provider():
    called = False
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace()))

    async def _create(**_kwargs):
        nonlocal called
        called = True
        return SimpleNamespace()

    client.chat.completions.create = _create

    with pytest.raises(HTTPException) as exc_info:
        await create_tracked_chat_completion(
            client=client,
            feature="advisor_message",
            model="gpt-4o-mini",
            user_id=None,
            messages=[{"role": "user", "content": "Hello"}],
        )

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail["kind"] == "llm_attribution"
    assert called is False


@pytest.mark.asyncio
async def test_token_capacity_without_customer_attribution_fails_closed(db):
    with pytest.raises(HTTPException) as exc_info:
        await llm_usage_utils.assert_llm_token_capacity(
            db,
            estimated_tokens=100,
        )

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail["kind"] == "llm_attribution"


@pytest.mark.asyncio
async def test_explicit_system_scope_can_call_provider_without_customer_reservation():
    response = SimpleNamespace(choices=[])
    calls = 0
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace()))

    async def _create(**_kwargs):
        nonlocal calls
        calls += 1
        return response

    client.chat.completions.create = _create

    result = await create_tracked_chat_completion(
        client=client,
        feature="system_maintenance",
        model="gpt-4o-mini",
        user_id=None,
        billing_scope="system",
        messages=[],
    )

    assert result is response
    assert calls == 1


@pytest.mark.asyncio
async def test_summarize_llm_usage_for_user_returns_totals(db):
    user = User(
        email="llm-usage@lorevia.app",
        username="llmusage",
        password_hash="hash",
        tier="author",
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
        return SimpleNamespace(
            id="tracked-reservation", operation="chat", user_id=kwargs["user_id"]
        )

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


@pytest.mark.asyncio
async def test_tracked_chat_completion_records_expected_provider_failures(monkeypatch):
    user_id = uuid.uuid4()
    reservation = SimpleNamespace(id="tracked-reservation", operation="chat", user_id=user_id)
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace()))
    failed: list[object] = []

    async def _provider_failure(**_kwargs):
        raise RuntimeError("provider unavailable")

    async def _reserve(**_kwargs):
        return reservation

    async def _fail(value):
        failed.append(value)

    client.chat.completions.create = _provider_failure
    monkeypatch.setattr("app.services.llm_control_service.reserve_llm_call", _reserve)
    monkeypatch.setattr("app.services.llm_control_service.fail_llm_reservation", _fail)

    with pytest.raises(RuntimeError, match="provider unavailable"):
        await create_tracked_chat_completion(
            client=client,
            feature="advisor_message",
            model="gpt-test",
            user_id=user_id,
            messages=[],
        )

    assert failed == [reservation]


@pytest.mark.asyncio
async def test_tracked_chat_completion_preserves_provider_error_when_failure_recording_fails(
    monkeypatch,
):
    user_id = uuid.uuid4()
    reservation = SimpleNamespace(id="tracked-reservation", operation="chat", user_id=user_id)
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace()))

    async def _provider_failure(**_kwargs):
        raise RuntimeError("provider unavailable")

    async def _reserve(**_kwargs):
        return reservation

    async def _fail(_reservation):
        raise SQLAlchemyError("database unavailable")

    client.chat.completions.create = _provider_failure
    monkeypatch.setattr("app.services.llm_control_service.reserve_llm_call", _reserve)
    monkeypatch.setattr("app.services.llm_control_service.fail_llm_reservation", _fail)

    with pytest.raises(RuntimeError, match="provider unavailable"):
        await create_tracked_chat_completion(
            client=client,
            feature="advisor_message",
            model="gpt-test",
            user_id=user_id,
            messages=[],
        )


@pytest.mark.asyncio
async def test_tracked_embedding_releases_reservation_on_unexpected_client_error(
    monkeypatch,
):
    user_id = uuid.uuid4()
    client = SimpleNamespace(embeddings=SimpleNamespace())
    failed = False

    async def _client_bug(**_kwargs):
        raise AssertionError("client invariant")

    async def _reserve(**kwargs):
        return SimpleNamespace(
            id="tracked-reservation",
            operation="embedding",
            user_id=kwargs["user_id"],
        )

    async def _fail(_reservation):
        nonlocal failed
        failed = True

    client.embeddings.create = _client_bug
    monkeypatch.setattr("app.services.llm_control_service.reserve_llm_call", _reserve)
    monkeypatch.setattr("app.services.llm_control_service.fail_llm_reservation", _fail)

    with pytest.raises(AssertionError, match="client invariant"):
        await create_tracked_embedding(
            client=client,
            feature="chapter_chunk_embedding",
            model="text-embedding-3-small",
            user_id=user_id,
            input="text",
        )

    assert failed is True


@pytest.mark.parametrize("operation", ["chat", "embedding"])
async def test_tracked_call_releases_circuit_permit_when_settlement_fails(monkeypatch, operation):
    user_id = uuid.uuid4()
    permit = object()
    released = []

    async def _return_permit(**_kwargs):
        return permit

    async def _release(value):
        released.append(value)

    async def _reserve(**_kwargs):
        return SimpleNamespace(id="reservation", user_id=user_id)

    async def _provider_response(**_kwargs):
        return SimpleNamespace(usage=None)

    async def _finish(*_args):
        raise SQLAlchemyError("settlement unavailable")

    monkeypatch.setattr(
        "app.services.llm_circuit_breaker_service.acquire_provider_circuit_permit",
        _return_permit,
    )
    monkeypatch.setattr(
        "app.services.llm_circuit_breaker_service.release_provider_circuit_permit",
        _release,
    )
    monkeypatch.setattr("app.services.llm_control_service.reserve_llm_call", _reserve)
    monkeypatch.setattr("app.services.llm_control_service.finish_llm_reservation", _finish)

    with pytest.raises(SQLAlchemyError, match="settlement unavailable"):
        if operation == "chat":
            client = SimpleNamespace(
                chat=SimpleNamespace(completions=SimpleNamespace(create=_provider_response))
            )
            await create_tracked_chat_completion(
                client=client,
                feature="chapter_summary_detailed",
                model="gpt-test",
                user_id=user_id,
                messages=[],
            )
        else:
            client = SimpleNamespace(embeddings=SimpleNamespace(create=_provider_response))
            await create_tracked_embedding(
                client=client,
                feature="chapter_chunk_embedding",
                model="text-embedding-3-small",
                user_id=user_id,
                input="text",
            )

    assert released == [permit]


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
async def test_token_capacity_reports_latest_eligible_reset_across_windows(db, monkeypatch):
    unique_suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"token-reset-{unique_suffix}@lorevia.app",
        username=f"tokenreset{unique_suffix}",
        password_hash="hash",
        tier="free",
    )
    db.add(user)
    await db.flush()
    now = datetime.now(UTC).replace(microsecond=0)
    user.created_at = now - timedelta(days=60)
    db.add_all(
        [
            LlmUsageEvent(
                user_id=user.id,
                provider="openai",
                model="gpt-test",
                operation="chat_completion",
                feature="manual_reprocess",
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=80,
                created_at=now - timedelta(days=6),
            ),
            LlmUsageEvent(
                user_id=user.id,
                provider="openai",
                model="gpt-test",
                operation="chat_completion",
                feature="manual_reprocess",
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=80,
                created_at=now - timedelta(hours=4),
            ),
        ]
    )
    await db.commit()
    monkeypatch.setattr(llm_usage_utils.settings, "FREE_LLM_TOKENS_5H", 100, raising=False)
    monkeypatch.setattr(llm_usage_utils.settings, "FREE_LLM_TOKENS_WEEK", 150, raising=False)
    monkeypatch.setattr(llm_usage_utils.settings, "FREE_LLM_TOKENS_MONTH", 1000, raising=False)

    with pytest.raises(HTTPException) as exc:
        await assert_manual_reprocess_token_capacity(db, user, estimated_tokens=30, now=now)

    detail = exc.value.detail
    assert detail["kind"] == "llm_tokens"
    assert detail["windows"] == ["5-hour", "weekly"]
    assert detail["auto_resume"] is True
    assert datetime.fromisoformat(detail["next_resume_at"]) == now + timedelta(days=1, seconds=1)


@pytest.mark.asyncio
async def test_token_request_larger_than_window_cap_is_marked_permanent(db, monkeypatch):
    unique_suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"token-permanent-{unique_suffix}@lorevia.app",
        username=f"tokenpermanent{unique_suffix}",
        password_hash="hash",
        tier="free",
    )
    db.add(user)
    await db.flush()
    user.created_at = datetime.now(UTC) - timedelta(days=60)
    await db.commit()
    monkeypatch.setattr(llm_usage_utils.settings, "FREE_LLM_TOKENS_5H", 100, raising=False)
    monkeypatch.setattr(llm_usage_utils.settings, "FREE_LLM_TOKENS_WEEK", 100, raising=False)
    monkeypatch.setattr(llm_usage_utils.settings, "FREE_LLM_TOKENS_MONTH", 100, raising=False)

    with pytest.raises(HTTPException) as exc:
        await assert_manual_reprocess_token_capacity(db, user, estimated_tokens=101)

    detail = exc.value.detail
    assert detail["kind"] == "llm_tokens"
    assert detail["auto_resume"] is False
    assert detail["permanent"] is True
    assert detail["next_resume_at"] is None


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
        email="embed-block@lorevia.app",
        username="embedblock",
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
