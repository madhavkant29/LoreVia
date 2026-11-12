from __future__ import annotations

import asyncio
import uuid
from types import SimpleNamespace

import pytest
from google.genai.errors import APIError as GeminiAPIError

from app.core import llm
from app.utils.llm_usage_utils import LLMIncompleteResponseError


class _FakeOpenAIClient:
    def __init__(self):
        self.closed = False

    async def close(self):
        self.closed = True

    def is_closed(self):
        return self.closed


@pytest.mark.asyncio
async def test_complete_with_fallback_tracks_openai_completion_without_duplicate_model(monkeypatch):
    captured: dict[str, object] = {}

    async def _fake_create_tracked_chat_completion(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="  Rejoin the story here.  "))]
        )

    monkeypatch.setattr(llm.settings, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(llm.settings, "GEMINI_API_KEY", None)
    monkeypatch.setattr(llm, "create_tracked_chat_completion", _fake_create_tracked_chat_completion)

    client = _FakeOpenAIClient()
    result = await llm.complete_with_fallback(
        system="System prompt",
        user="User prompt",
        openai_model="gpt-test",
        openai_client=client,
        usage_feature="reader_recall",
        usage_user_id=uuid.uuid4(),
    )

    assert result == "Rejoin the story here."
    assert captured["model"] == "gpt-test"
    assert captured["messages"] == [
        {"role": "system", "content": "System prompt"},
        {"role": "user", "content": "User prompt"},
    ]
    assert client.closed is False


@pytest.mark.asyncio
async def test_complete_with_fallback_forwards_usage_db(monkeypatch):
    captured: dict[str, object] = {}

    async def _fake_create_tracked_chat_completion(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(message=SimpleNamespace(content="Tracked with current session."))
            ]
        )

    usage_db = object()
    monkeypatch.setattr(llm.settings, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(llm.settings, "GEMINI_API_KEY", None)
    monkeypatch.setattr(llm, "create_tracked_chat_completion", _fake_create_tracked_chat_completion)

    result = await llm.complete_with_fallback(
        system="System prompt",
        user="User prompt",
        openai_model="gpt-test",
        usage_feature="reader_recall",
        usage_user_id=uuid.uuid4(),
        usage_db=usage_db,
    )

    assert result == "Tracked with current session."
    assert captured["db"] is usage_db


@pytest.mark.asyncio
async def test_structured_completion_rejects_provider_truncation_even_with_valid_json(monkeypatch):
    async def fake_completion(**_kwargs):
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason="length",
                    message=SimpleNamespace(content='{"characters":[],"relationships":[]}'),
                )
            ]
        )

    monkeypatch.setattr(llm.settings, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(llm.settings, "GEMINI_API_KEY", None)
    monkeypatch.setattr(llm, "create_tracked_chat_completion", fake_completion)

    with pytest.raises(LLMIncompleteResponseError, match="llm_response_incomplete"):
        await llm.complete_with_fallback(
            system="Extract people.",
            user="Mara spoke to Ilya.",
            openai_model="gpt-test",
            openai_client=_FakeOpenAIClient(),
            response_format={"type": "json_object"},
            require_complete_output=True,
            usage_user_id=uuid.uuid4(),
        )


@pytest.mark.asyncio
async def test_complete_with_fallback_retries_transient_errors(monkeypatch):
    call_count = [0]

    async def _mock_completion(**kwargs):
        call_count[0] += 1
        if call_count[0] < 2:
            import httpx

            raise httpx.ConnectError("transient connection error")
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="Success after retry"))]
        )

    monkeypatch.setattr(llm.settings, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(llm.settings, "GEMINI_API_KEY", None)
    monkeypatch.setattr(llm, "create_tracked_chat_completion", _mock_completion)

    result = await llm.complete_with_fallback(
        system="System prompt",
        user="User prompt",
        openai_model="gpt-test",
        usage_feature="reader_recall",
        usage_user_id=uuid.uuid4(),
    )

    assert result == "Success after retry"
    assert call_count[0] == 2


@pytest.mark.asyncio
async def test_complete_with_fallback_can_disable_transient_retry_for_capped_review(
    monkeypatch,
):
    import httpx

    calls = 0

    async def failed_completion(**_kwargs):
        nonlocal calls
        calls += 1
        raise httpx.ConnectError("transient connection error")

    monkeypatch.setattr(llm.settings, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(llm.settings, "GEMINI_API_KEY", None)
    monkeypatch.setattr(llm, "create_tracked_chat_completion", failed_completion)

    with pytest.raises(httpx.ConnectError):
        await llm.complete_with_fallback(
            system="Review source evidence.",
            user="Review one bounded passage.",
            openai_model="gpt-test",
            openai_client=_FakeOpenAIClient(),
            retry_transient_openai=False,
            usage_user_id=uuid.uuid4(),
        )

    assert calls == 1


@pytest.mark.asyncio
async def test_complete_with_fallback_no_retry_on_400(monkeypatch):
    call_count = [0]

    async def _mock_openai_completion(**kwargs):
        call_count[0] += 1
        raise ValueError("bad request - not transient")

    async def _mock_gemini(**kwargs):
        return "Gemini fallback"

    monkeypatch.setattr(llm.settings, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(llm.settings, "GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setattr(llm, "create_tracked_chat_completion", _mock_openai_completion)
    monkeypatch.setattr(llm, "_complete_with_gemini", _mock_gemini)

    result = await llm.complete_with_fallback(
        system="System prompt",
        user="User prompt",
        openai_model="gpt-test",
        gemini_model="gemini-test",
        usage_feature="reader_recall",
        usage_user_id=None,
        usage_billing_scope="system",
    )

    assert result == "Gemini fallback"
    assert call_count[0] == 1


@pytest.mark.asyncio
async def test_complete_with_fallback_retries_503_then_falls_back_to_gemini(monkeypatch):
    call_count = [0]

    async def _mock_openai_completion(**kwargs):
        call_count[0] += 1
        import httpx

        raise httpx.RemoteProtocolError("server error")

    async def _mock_gemini(**kwargs):
        return "Gemini fallback after retries"

    monkeypatch.setattr(llm.settings, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(llm.settings, "GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setattr(llm, "create_tracked_chat_completion", _mock_openai_completion)
    monkeypatch.setattr(llm, "_complete_with_gemini", _mock_gemini)

    result = await llm.complete_with_fallback(
        system="System prompt",
        user="User prompt",
        openai_model="gpt-test",
        gemini_model="gemini-test",
        usage_feature="reader_recall",
        usage_user_id=None,
        usage_billing_scope="system",
    )

    assert result == "Gemini fallback after retries"
    assert call_count[0] == 2


@pytest.mark.asyncio
async def test_complete_with_fallback_propagates_unexpected_openai_client_bugs(monkeypatch):
    async def _buggy_openai_completion(**kwargs):
        raise AssertionError("client invariant")

    async def _mock_gemini(**kwargs):
        return "should not be used"

    monkeypatch.setattr(llm.settings, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(llm.settings, "GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setattr(llm, "create_tracked_chat_completion", _buggy_openai_completion)
    monkeypatch.setattr(llm, "_complete_with_gemini", _mock_gemini)

    with pytest.raises(AssertionError, match="client invariant"):
        await llm.complete_with_fallback(
            system="System prompt",
            user="User prompt",
            openai_model="gpt-test",
            gemini_model="gemini-test",
            usage_feature="reader_recall",
            usage_user_id=None,
            usage_billing_scope="system",
        )


def test_is_transient_openai_error_httpx():
    import httpx

    assert llm._is_transient_openai_error(httpx.ConnectError("test")) is True
    assert llm._is_transient_openai_error(httpx.TimeoutException("test")) is True
    assert llm._is_transient_openai_error(httpx.RemoteProtocolError("test")) is True


def test_is_transient_openai_error_non_transient():
    assert llm._is_transient_openai_error(ValueError("test")) is False
    assert llm._is_transient_openai_error(Exception("test")) is False


def test_get_openai_client_reuses_instance(monkeypatch):
    monkeypatch.setattr(llm.settings, "OPENAI_API_KEY", "test-key")

    client1 = llm.get_openai_client()
    client2 = llm.get_openai_client()

    assert client1 is client2


def test_get_openai_client_disables_hidden_sdk_retries(monkeypatch):
    captured: dict[str, object] = {}
    client = object()

    def fake_openai(**kwargs):
        captured.update(kwargs)
        return client

    monkeypatch.setattr(llm, "_openai_client", None)
    monkeypatch.setattr(llm, "_openai_clients", {})
    monkeypatch.setattr(llm, "AsyncOpenAI", fake_openai)
    monkeypatch.setattr(llm.settings, "OPENAI_API_KEY", "test-key")

    assert llm.get_openai_client() is client
    assert captured == {"api_key": "test-key", "max_retries": 0}


@pytest.mark.asyncio
async def test_openai_registry_is_loop_aware_and_closes_owned_clients(monkeypatch):
    first = _FakeOpenAIClient()
    second = _FakeOpenAIClient()
    clients = iter([first, second])

    monkeypatch.setattr(llm, "_openai_clients", {})
    monkeypatch.setattr(llm, "AsyncOpenAI", lambda **_kwargs: next(clients))
    monkeypatch.setattr(llm, "_openai_client_registry_key", lambda: (101, 1))
    assert llm.get_openai_client() is first
    assert llm.get_openai_client() is first

    monkeypatch.setattr(llm, "_openai_client_registry_key", lambda: (101, 2))
    assert llm.get_openai_client() is second

    await llm.close_openai_clients()
    assert first.closed is second.closed is True


@pytest.mark.asyncio
async def test_get_openai_client_recreates_closed_cached_client(monkeypatch):
    first = _FakeOpenAIClient()
    second = _FakeOpenAIClient()
    clients = iter([first, second])
    monkeypatch.setattr(llm, "_openai_clients", {})
    monkeypatch.setattr(llm, "AsyncOpenAI", lambda **_kwargs: next(clients))

    assert llm.get_openai_client() is first
    await first.close()
    assert llm.get_openai_client() is second
    assert llm.get_openai_client() is second
    await llm.close_openai_clients()
    assert second.closed is True


def test_get_openai_client_does_not_reuse_a_client_from_a_previous_event_loop(monkeypatch):
    first = _FakeOpenAIClient()
    second = _FakeOpenAIClient()
    clients = iter([first, second])
    monkeypatch.setattr(llm, "_openai_clients", {})
    monkeypatch.setattr(llm, "AsyncOpenAI", lambda **_kwargs: next(clients))

    async def resolve():
        return llm.get_openai_client(), asyncio.get_running_loop()

    first_client, first_loop = asyncio.run(resolve())
    second_client, second_loop = asyncio.run(resolve())

    assert first_client is first
    assert second_client is second
    assert first_loop is not second_loop
    assert {key[1] for key in llm._openai_clients} == {first_loop, second_loop}
    asyncio.run(llm.close_openai_clients())
    assert first.closed is second.closed is True


def test_get_gemini_client_sets_timeout_and_disables_hidden_sdk_retries(monkeypatch):
    from google import genai

    captured: dict[str, object] = {}
    client = object()

    def fake_gemini_client(**kwargs):
        captured.update(kwargs)
        return client

    monkeypatch.setattr(llm, "_gemini_client", None)
    monkeypatch.setattr(llm, "_gemini_client_cache_key", None)
    monkeypatch.setattr(llm.settings, "GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setattr(llm.settings, "GEMINI_REQUEST_TIMEOUT_SECONDS", 45)
    monkeypatch.setattr(genai, "Client", fake_gemini_client)

    assert llm._get_gemini_client() is client
    http_options = captured["http_options"]
    assert http_options.timeout == 45_000
    assert http_options.retry_options.attempts == 1


def test_gemini_error_classification_and_usage_counts():
    assert llm._is_transient_gemini_error(
        GeminiAPIError(503, {"message": "temporarily unavailable"})
    )
    assert not llm._is_transient_gemini_error(GeminiAPIError(400, {"message": "invalid request"}))
    usage = SimpleNamespace(
        prompt_token_count=120,
        candidates_token_count=30,
        total_token_count=150,
    )
    assert llm._gemini_usage_counts(SimpleNamespace(usage_metadata=usage)) == (120, 30, 150)


def test_get_openai_client_returns_external_when_provided(monkeypatch):
    monkeypatch.setattr(llm.settings, "OPENAI_API_KEY", "test-key")

    external = object()
    result = llm.get_openai_client(external)

    assert result is external
