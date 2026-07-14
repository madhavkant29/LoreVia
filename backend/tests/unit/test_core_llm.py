from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core import llm


class _FakeOpenAIClient:
    def __init__(self):
        self.closed = False

    async def close(self):
        self.closed = True


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
        usage_db=usage_db,
    )

    assert result == "Tracked with current session."
    assert captured["db"] is usage_db


@pytest.mark.asyncio
async def test_complete_with_fallback_retries_transient_errors(monkeypatch):
    call_count = [0]

    async def _mock_completion(**kwargs):
        call_count[0] += 1
        if call_count[0] < 3:
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
    )

    assert result == "Success after retry"
    assert call_count[0] == 3


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
    )

    assert result == "Gemini fallback after retries"
    assert call_count[0] == 3


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

    client1 = llm._get_openai_client()
    client2 = llm._get_openai_client()

    assert client1 is client2


def test_get_openai_client_returns_external_when_provided(monkeypatch):
    monkeypatch.setattr(llm.settings, "OPENAI_API_KEY", "test-key")

    external = object()
    result = llm._get_openai_client(external)

    assert result is external
