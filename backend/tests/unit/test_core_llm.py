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
