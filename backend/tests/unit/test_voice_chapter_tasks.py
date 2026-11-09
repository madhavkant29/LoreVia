"""Caught voice-review failures must remain visible to operators."""

import asyncio
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import sentry_sdk

from app.services import voice_chapter_review_jobs_service, voice_chapter_review_service
from app.workers.tasks import voice_chapter_tasks


def test_voice_chapter_task_reports_caught_failure_and_marks_job_failed(monkeypatch):
    job = SimpleNamespace(id=uuid.uuid4())
    db = SimpleNamespace(rollback=AsyncMock())
    failed = AsyncMock(return_value=True)
    reported = Mock()

    class Session:
        async def __aenter__(self):
            return db

        async def __aexit__(self, *_args):
            return False

    async def claim(*_args, **_kwargs):
        return job

    async def process(*_args, **_kwargs):
        raise RuntimeError("private manuscript text")

    monkeypatch.setattr("app.core.database.AsyncSessionLocal", Session)
    monkeypatch.setattr(voice_chapter_review_jobs_service, "claim_voice_chapter_job", claim)
    monkeypatch.setattr(voice_chapter_review_jobs_service, "update_voice_chapter_job", failed)
    monkeypatch.setattr(voice_chapter_review_service, "process_voice_chapter_job", process)
    monkeypatch.setattr(voice_chapter_tasks, "run_worker_coro", asyncio.run)
    monkeypatch.setattr(sentry_sdk, "capture_message", reported)

    result = voice_chapter_tasks.review_voice_chapter_task.run(job_id=str(job.id))

    assert result == "failed"
    reported.assert_called_once_with("voice_chapter_review_failed", level="error")
    assert "private manuscript text" not in str(reported.call_args)
    failed.assert_awaited_once()
    assert failed.await_args.kwargs["status"] == "failed"
    db.rollback.assert_awaited_once()
