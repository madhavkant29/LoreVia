from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from app.services import extraction_budget_service as budget_service


class ScalarResult:
    def __init__(self, value: int):
        self.value = value

    def scalar(self):
        return self.value


class FakeDb:
    def __init__(self, used_tokens: int = 0) -> None:
        self.used_tokens = used_tokens
        self.execute_calls = 0
        self.commits = 0

    async def execute(self, _statement):
        self.execute_calls += 1
        return ScalarResult(self.used_tokens)

    async def commit(self) -> None:
        self.commits += 1


@pytest.mark.asyncio
async def test_apply_ingestion_token_budget_returns_all_chapters_for_paid_user(monkeypatch):
    monkeypatch.setattr(budget_service, "has_paid_reading_access", lambda _user: True)
    monkeypatch.setattr(budget_service, "count_tokens", lambda text: len(str(text).split()))

    db = FakeDb()
    chapters = [{"text": "one two"}, {"text": "three four five"}]

    result = await budget_service.apply_ingestion_token_budget(
        db,
        book=SimpleNamespace(id=uuid.uuid4()),
        user=SimpleNamespace(id=uuid.uuid4()),
        all_chapters=chapters,
    )

    assert result["error"] is None
    assert result["ai_chapters"] == chapters
    assert result["processed_tokens"] == 5
    assert result["was_truncated"] is False
    assert db.execute_calls == 0


@pytest.mark.asyncio
async def test_apply_ingestion_token_budget_truncates_free_user(monkeypatch):
    monkeypatch.setattr(budget_service, "has_paid_reading_access", lambda _user: False)
    monkeypatch.setattr(budget_service.settings, "FREE_TOTAL_TOKEN_BUDGET", 5)
    monkeypatch.setattr(budget_service, "count_tokens", lambda text: len(str(text).split()))

    chapters = [{"text": "one two"}, {"text": "three four"}, {"text": "five six"}]

    result = await budget_service.apply_ingestion_token_budget(
        FakeDb(used_tokens=1),
        book=SimpleNamespace(id=uuid.uuid4()),
        user=SimpleNamespace(id=uuid.uuid4()),
        all_chapters=chapters,
    )

    assert result["error"] is None
    assert result["ai_chapters"] == chapters[:2]
    assert result["processed_tokens"] == 4
    assert result["was_truncated"] is True


@pytest.mark.asyncio
async def test_apply_ingestion_token_budget_marks_error_when_budget_exhausted(monkeypatch):
    monkeypatch.setattr(budget_service, "has_paid_reading_access", lambda _user: False)
    monkeypatch.setattr(budget_service.settings, "FREE_TOTAL_TOKEN_BUDGET", 5)
    monkeypatch.setattr(budget_service, "count_tokens", lambda text: len(str(text).split()))

    db = FakeDb(used_tokens=5)
    result = await budget_service.apply_ingestion_token_budget(
        db,
        book=SimpleNamespace(id=uuid.uuid4()),
        user=SimpleNamespace(id=uuid.uuid4()),
        all_chapters=[{"text": "one two"}],
    )

    assert result["error"] == "budget_exhausted"
    assert result["processed_tokens"] == 0
    assert db.execute_calls == 2
    assert db.commits == 1


@pytest.mark.asyncio
async def test_apply_ingestion_token_budget_marks_error_when_first_chapter_too_large(monkeypatch):
    monkeypatch.setattr(budget_service, "has_paid_reading_access", lambda _user: False)
    monkeypatch.setattr(budget_service.settings, "FREE_TOTAL_TOKEN_BUDGET", 5)
    monkeypatch.setattr(budget_service, "count_tokens", lambda text: len(str(text).split()))

    db = FakeDb(used_tokens=3)
    result = await budget_service.apply_ingestion_token_budget(
        db,
        book=SimpleNamespace(id=uuid.uuid4()),
        user=SimpleNamespace(id=uuid.uuid4()),
        all_chapters=[{"text": "one two three"}],
    )

    assert result["error"] == "insufficient_remaining_budget"
    assert result["remaining_budget"] == 2
    assert db.execute_calls == 2
    assert db.commits == 1
