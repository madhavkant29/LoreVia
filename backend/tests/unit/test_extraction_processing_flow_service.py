from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from app.services import extraction_processing_flow_service as flow_service


class FakeDb:
    def __init__(self, user: SimpleNamespace | None = None) -> None:
        self.commits = 0
        self.user = user

    async def commit(self) -> None:
        self.commits += 1

    async def get(self, _model, _id):
        return self.user


@pytest.mark.asyncio
async def test_finalize_book_completion_returns_false_when_book_not_complete(monkeypatch):
    async def claim(_db, _book_id):
        return False

    monkeypatch.setattr(flow_service, "_claim_book_completion", claim)

    db = FakeDb()
    completed = await flow_service.finalize_book_completion_after_chapter(
        db,
        book=SimpleNamespace(id=uuid.uuid4()),
        chapter=SimpleNamespace(title="Chapter 1"),
        chapter_number=1,
        processed_count=1,
        processing_total=2,
        queue_wait_ms=None,
        extraction_diagnostics={},
    )

    assert completed is False
    assert db.commits == 1


@pytest.mark.asyncio
async def test_finalize_book_completion_updates_ready_state_and_sends_notification(monkeypatch):
    sent: list[dict] = []

    async def claim(_db, _book_id):
        return True

    async def reconcile_aliases(_db, **_kwargs):
        return 1

    async def reconcile_relationships(_db, **_kwargs):
        return {"merged": 0}

    async def collect_stats(_db, _book):
        return SimpleNamespace(
            analysis_complete=True,
            character_count=3,
            relationship_count=2,
            plot_thread_count=1,
            continuity_issue_count=0,
        )

    def processing_state(*, analysis_complete):
        assert analysis_complete is True
        return "ready", "ready"

    def update_state(_book, **kwargs):
        return {"processing": kwargs}

    async def complete_rebuild(_db, _book):
        _book.rebuild_completed = True

    async def upsert_notification(_db, _book, _stats):
        return SimpleNamespace(), True

    async def send_email(email, **kwargs):
        sent.append({"email": email, **kwargs})

    monkeypatch.setattr(flow_service, "_claim_book_completion", claim)
    monkeypatch.setattr(
        flow_service,
        "reconcile_pending_first_name_alias_candidates",
        reconcile_aliases,
    )
    monkeypatch.setattr(flow_service, "reconcile_extracted_relationships", reconcile_relationships)
    monkeypatch.setattr(flow_service, "collect_book_ready_stats", collect_stats)
    monkeypatch.setattr(flow_service, "processing_state_for_completed_extraction", processing_state)
    monkeypatch.setattr(flow_service, "update_book_processing_state", update_state)
    monkeypatch.setattr(flow_service, "complete_rebuild_if_ready", complete_rebuild)
    monkeypatch.setattr(flow_service, "upsert_book_ready_notification", upsert_notification)
    monkeypatch.setattr(flow_service, "send_processing_complete_with_stats", send_email)

    book = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        title="The Test Book",
        mode="reader",
        total_chapters=1,
        writer_workspace={},
    )
    db = FakeDb(user=SimpleNamespace(email="author@example.test"))

    completed = await flow_service.finalize_book_completion_after_chapter(
        db,
        book=book,
        chapter=SimpleNamespace(title="Chapter 1"),
        chapter_number=1,
        processed_count=1,
        processing_total=1,
        queue_wait_ms=25,
        extraction_diagnostics={"summary": "ok"},
    )

    assert completed is True
    assert book.status == "ready"
    assert book.rebuild_completed is True
    assert book.writer_workspace["processing"]["stage"] == "ready"
    assert db.commits == 1
    assert sent == [
        {
            "email": "author@example.test",
            "book_title": "The Test Book",
            "character_count": 3,
            "relationship_count": 2,
            "plot_thread_count": 1,
            "continuity_issue_count": 0,
        }
    ]
